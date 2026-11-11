"""LightGBM variants and probability-averaged ensembles.

Uses the same two validation schemes as compare_model_families.py.
This is the experiment that chose the final LightGBM + CatBoost + LogReg blend.

Usage:
    python scripts/tune_lightgbm_and_ensembles.py
"""
import pickle
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make belt_defect importable

import pandas as pd

from belt_defect import config
from belt_defect.evaluation import ValidationProba, run_validation_schemes, score_validation
from belt_defect.feature_engineering import build_features, select_model_features, split_column_types
from belt_defect.models import fit_predict_proba, make_catboost, make_lightgbm, make_logistic_regression
from belt_defect.preprocessing import load_training_data

warnings.filterwarnings("ignore")

BASE_EXCLUDED = config.EXCLUDED_FEATURES  # ["Technician_ID", "Month"]

# Name -> (LightGBM param overrides, excluded features)
LIGHTGBM_VARIANTS = {
    "lgb_base": ({}, BASE_EXCLUDED),
    "lgb_+month": ({}, ["Technician_ID"]),
    "lgb_+tech": ({}, ["Month"]),
    "lgb_spw1": (dict(scale_pos_weight=1), BASE_EXCLUDED),
    "lgb_spw15": (dict(scale_pos_weight=15), BASE_EXCLUDED),
    "lgb_leaves7_1000": (dict(num_leaves=7, n_estimators=1000, learning_rate=0.02), BASE_EXCLUDED),
    "lgb_leaves31": (dict(num_leaves=31, min_child_samples=30), BASE_EXCLUDED),
    "lgb_reg": (dict(reg_lambda=5, min_child_samples=40, colsample_bytree=0.6), BASE_EXCLUDED),
}


def average_proba(proba_by_model: dict, names) -> ValidationProba:
    """Equal-weight probability average (keeps thresholds on the probability scale)."""
    members = [proba_by_model[n] for n in names]
    return ValidationProba(*(sum(m[i] for m in members) / len(members) for i in range(3)))


def main():
    train_df = load_training_data(config.TRAIN_PATH, sort_by_date=True)  # sorted for the temporal split
    y = train_df[config.LABEL_COLUMN].values
    all_features = build_features(train_df)

    proba_by_model, results = {}, []

    def evaluate(name, fit_predict, X):
        proba_by_model[name] = run_validation_schemes(fit_predict, X, y)
        results.append(score_validation(name, y, proba_by_model[name]))
        print({k: round(v, 3) if isinstance(v, float) else v for k, v in results[-1].items()}, flush=True)

    # --- LightGBM variants (params and feature sets) ---
    for name, (overrides, excluded) in LIGHTGBM_VARIANTS.items():
        evaluate(name, lambda Xf, yf, Xs, _seed, o=overrides: fit_predict_proba(make_lightgbm(0, **o), Xf, yf, Xs),
                 select_model_features(all_features, excluded))

    # --- CatBoost and logistic regression, as ensemble members ---
    X_base = select_model_features(all_features, BASE_EXCLUDED)
    numeric_columns, categorical_columns = split_column_types(X_base)
    evaluate("cat", lambda Xf, yf, Xs, _seed: fit_predict_proba(
        make_catboost(categorical_columns, 0), Xf, yf, Xs, string_categoricals=categorical_columns), X_base)
    evaluate("lr", lambda Xf, yf, Xs, _seed: fit_predict_proba(
        make_logistic_regression(numeric_columns, categorical_columns), Xf, yf, Xs), X_base)

    # --- Ensembles: best LightGBM (by CV F1 + time F1) with the others ---
    lightgbm_rows = [r for r in results if r["Model"].startswith("lgb")]
    best_lightgbm = max(lightgbm_rows, key=lambda r: r["CV_F1"] + r["Time_F1"])["Model"]
    ensembles = [
        (best_lightgbm, "cat"),
        (best_lightgbm, "lr"),
        (best_lightgbm, "cat", "lr"),
        ("lgb_base", "lgb_leaves7_1000", "lgb_reg"),
    ]
    for members in ensembles:
        name = "+".join(members)
        proba_by_model[name] = average_proba(proba_by_model, members)
        results.append(score_validation(name, y, proba_by_model[name]))
        print({k: round(v, 3) if isinstance(v, float) else v for k, v in results[-1].items()}, flush=True)

    # --- Save ---
    results_df = pd.DataFrame(results).round(3)
    results_df["avg_F1"] = ((results_df.CV_F1 + results_df.Time_F1) / 2).round(3)
    print(results_df.sort_values("avg_F1", ascending=False).to_string())
    config.EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(config.EXPERIMENTS_DIR / "lightgbm_ensemble_experiments.csv", index=False)
    with open(config.EXPERIMENTS_DIR / "lightgbm_ensemble_probabilities.pkl", "wb") as f:
        pickle.dump({k: tuple(v) for k, v in proba_by_model.items()}, f)


if __name__ == "__main__":
    main()
