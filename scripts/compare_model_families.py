"""Compare model families on defect-class F1 (threshold tuned per model).

Validation schemes:
  A) 5-fold stratified CV x 2 repeats on all rows
  B) Temporal: train on first 80% by date (threshold from inner CV), score on last 20%

Usage:
    python scripts/compare_model_families.py              # all models
    python scripts/compare_model_families.py LightGBM CatBoost
"""
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make belt_defect importable

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.pipeline import make_pipeline

from belt_defect import config
from belt_defect.evaluation import run_validation_schemes, score_validation
from belt_defect.feature_engineering import build_features, select_model_features, split_column_types
from belt_defect.models import (fit_predict_proba, make_catboost, make_lightgbm, make_logistic_regression,
                                make_preprocessor)
from belt_defect.preprocessing import load_training_data

warnings.filterwarnings("ignore")


def model_builders(numeric_columns, categorical_columns) -> dict:
    """Name -> zero-arg builder for each candidate model."""
    unscaled = lambda: make_preprocessor(numeric_columns, categorical_columns, scale_numeric=False)
    return {
        "LogReg": lambda: make_logistic_regression(numeric_columns, categorical_columns),
        "RandomForest": lambda: make_pipeline(unscaled(), RandomForestClassifier(
            n_estimators=500, min_samples_leaf=3, class_weight="balanced_subsample", n_jobs=-1, random_state=0)),
        "ExtraTrees": lambda: make_pipeline(unscaled(), ExtraTreesClassifier(
            n_estimators=600, min_samples_leaf=3, class_weight="balanced_subsample", n_jobs=-1, random_state=0)),
        "HistGB": lambda: HistGradientBoostingClassifier(
            learning_rate=0.05, max_iter=400, max_leaf_nodes=15, l2_regularization=1.0,
            categorical_features="from_dtype", class_weight="balanced", random_state=0),
        "LightGBM": lambda: make_lightgbm(seed=0),
        "XGBoost": lambda: xgb.XGBClassifier(
            n_estimators=500, learning_rate=0.03, max_depth=4, subsample=0.8, colsample_bytree=0.8,
            min_child_weight=2, reg_lambda=1.0, scale_pos_weight=5, enable_categorical=True,
            tree_method="hist", eval_metric="aucpr", random_state=0),
        "CatBoost": lambda: make_catboost(categorical_columns, seed=0),
    }


def main():
    train_df = load_training_data(config.TRAIN_PATH, sort_by_date=True)  # sorted for the temporal split
    y = train_df[config.LABEL_COLUMN].values
    X = select_model_features(build_features(train_df))
    numeric_columns, categorical_columns = split_column_types(X)

    builders = model_builders(numeric_columns, categorical_columns)
    selected = sys.argv[1:] or list(builders)
    oof_dir = config.EXPERIMENTS_DIR / "oof_probabilities"
    oof_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for name in selected:
        build = builders[name]
        string_cats = categorical_columns if name == "CatBoost" else None

        # Fixed model seed; the CV seed only changes the folds
        def fit_predict(X_fit, y_fit, X_score, _seed):
            return fit_predict_proba(build(), X_fit, y_fit, X_score, string_categoricals=string_cats)

        start = time.time()
        proba = run_validation_schemes(fit_predict, X, y)
        row = score_validation(name, y, proba)
        row["seconds"] = time.time() - start
        results.append(row)
        np.save(oof_dir / f"{name}.npy", proba.cv)
        print(row, flush=True)

    results_df = pd.DataFrame(results).round(3)
    print(results_df.to_string())
    suffix = "" if not sys.argv[1:] else "_" + "_".join(selected)
    results_df.to_csv(config.EXPERIMENTS_DIR / f"model_comparison{suffix}.csv", index=False)


if __name__ == "__main__":
    main()
