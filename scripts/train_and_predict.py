"""Train the final blend and write the submission file.

Final model: average of LightGBM + CatBoost + logistic regression probabilities.
Threshold: from 5-fold x 3-repeat out-of-fold probabilities on all training rows.

Usage (all arguments optional; defaults point to data/raw and outputs/):
    python scripts/train_and_predict.py [train.xlsx] [test_inputs.csv] [template.csv] [predictions.csv]
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make belt_defect importable

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score

from belt_defect import config
from belt_defect.evaluation import out_of_fold_proba, recall_leaning_threshold
from belt_defect.feature_engineering import align_categories, build_features, select_model_features, split_column_types
from belt_defect.models import blend_fit_predict
from belt_defect.preprocessing import clean_raw_data, load_test_inputs, load_training_data

warnings.filterwarnings("ignore")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("train_path", nargs="?", default=config.TRAIN_PATH)
    parser.add_argument("test_path", nargs="?", default=config.TEST_INPUTS_PATH)
    parser.add_argument("template_path", nargs="?", default=config.SUBMISSION_TEMPLATE_PATH)
    parser.add_argument("output_path", nargs="?", default=config.SUBMISSION_PATH)
    return parser.parse_args()


def write_submission(template_path, record_ids, predicted_labels, output_path) -> pd.DataFrame:
    """Write predictions in template row order and check the format."""
    template = pd.read_csv(template_path, dtype=str)
    label_by_id = dict(zip(record_ids.astype(str), predicted_labels))
    missing_ids = [rid for rid in template.Record_ID if rid not in label_by_id]
    assert not missing_ids, f"{len(missing_ids)} template IDs not in test inputs, e.g. {missing_ids[:3]}"

    submission = pd.DataFrame({
        config.ID_COLUMN: template.Record_ID,
        config.TARGET_COLUMN: [label_by_id[rid] for rid in template.Record_ID],
    })
    assert len(submission) == len(template)
    assert submission[config.ID_COLUMN].is_unique
    assert submission[config.TARGET_COLUMN].isin(["Yes", "No"]).all()

    # Plain "\n" line endings, no index, exact header
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{config.ID_COLUMN},{config.TARGET_COLUMN}\n")
        for rid, label in zip(submission[config.ID_COLUMN], submission[config.TARGET_COLUMN]):
            f.write(f"{rid},{label}\n")
    return submission


def main():
    args = parse_args()

    # --- Load data and build features ---
    train_df = load_training_data(args.train_path)
    test_raw = load_test_inputs(args.test_path)
    test_df = clean_raw_data(test_raw)

    X_train = select_model_features(build_features(train_df))
    X_test = select_model_features(build_features(test_df))
    numeric_columns, categorical_columns = split_column_types(X_train)
    X_train, X_test = align_categories(X_train, X_test, categorical_columns)
    y_train = train_df[config.LABEL_COLUMN].values

    def fit_predict(X_fit, y_fit, X_score, seed):
        return blend_fit_predict(X_fit, y_fit, X_score, seed, numeric_columns, categorical_columns)

    # --- 1) Out-of-fold probabilities -> decision threshold ---
    oof_proba = out_of_fold_proba(fit_predict, X_train, y_train, config.FINAL_MODEL_SEEDS)
    # Lowest threshold within 0.01 F1 of the best: leans to recall, since the defect rate trends up
    threshold, best_threshold, best_f1 = recall_leaning_threshold(y_train, oof_proba, config.F1_TOLERANCE)
    oof_pred = oof_proba >= threshold
    oof_metrics = dict(
        threshold=threshold,
        best_oof_threshold=best_threshold,
        best_oof_F1=best_f1,
        F1=f1_score(y_train, oof_pred),
        Precision=precision_score(y_train, oof_pred),
        Recall=recall_score(y_train, oof_pred),
        predicted_yes_rate=float(oof_pred.mean()),
        train_yes_rate=float(y_train.mean()),
    )
    print("OOF:", json.dumps({k: round(v, 4) for k, v in oof_metrics.items()}))

    # --- 2) Fit on all training rows (seed-averaged) and score test ---
    test_proba = np.mean([fit_predict(X_train, y_train, X_test, seed) for seed in config.FINAL_MODEL_SEEDS], axis=0)
    test_labels = np.where(test_proba >= threshold, "Yes", "No")

    # --- 3) Save submission and diagnostics ---
    submission = write_submission(args.template_path, test_raw[config.ID_COLUMN], test_labels, args.output_path)
    n_yes = int((submission[config.TARGET_COLUMN] == "Yes").sum())
    print(f"Wrote {args.output_path}: {len(submission)} rows, {n_yes} Yes "
          f"({n_yes / len(submission):.1%}); threshold {threshold:.4f}")

    config.METRICS_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({config.ID_COLUMN: test_raw[config.ID_COLUMN], "defect_probability": test_proba}) \
        .to_csv(config.PREDICTIONS_DIR / "test_probabilities.csv", index=False)
    with open(config.METRICS_DIR / "oof_metrics.json", "w") as f:
        json.dump(oof_metrics, f, indent=2)
    np.save(config.METRICS_DIR / "oof_probabilities.npy", oof_proba)


if __name__ == "__main__":
    main()
