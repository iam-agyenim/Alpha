"""Check whether the test period's predicted defect rate is plausible.

Compares test inputs with recent training rows: monthly defect rates, feature drift,
missing values, category mix, adversarial validation and high-risk row shares.
Run after train_and_predict.py (reads the submission file).

Usage:
    python scripts/check_test_distribution_shift.py
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make belt_defect importable

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from belt_defect import config
from belt_defect.feature_engineering import build_features
from belt_defect.preprocessing import clean_raw_data, load_test_inputs, load_training_data

warnings.filterwarnings("ignore")
LABEL = config.LABEL_COLUMN
RECENT_ROWS = 2000                        # same size as the test set
CALIB_LOAD_HIGH, CALIB_LOAD_VERY_HIGH = 60, 90
TENSION_ERROR_HIGH_PCT = 8


def pct(series) -> float:
    return round(series.mean() * 100, 1)


def load_with_features():
    """Train (actual labels) and test (predicted labels), both with engineered columns."""
    train = load_training_data(config.TRAIN_PATH, sort_by_date=True)
    test = clean_raw_data(load_test_inputs(config.TEST_INPUTS_PATH))
    test = test.merge(pd.read_csv(config.SUBMISSION_PATH), on=config.ID_COLUMN)  # adds predicted Defect_Found
    test[LABEL] = (test[config.TARGET_COLUMN] == "Yes").astype(int)
    for df in (train, test):
        features = build_features(df)
        df["Calib_Load"] = features.Calib_Load
        df["Tension_Dev_Abs_Pct"] = features.Tension_Dev_Abs_Pct
        df["month"] = df[config.DATE_COLUMN].dt.to_period("M")
    return train, test


def monthly_summary(df) -> pd.DataFrame:
    """Defect rate and its main drivers per month."""
    return df.groupby("month").agg(
        defect_rate_pct=(LABEL, pct), rows=(LABEL, "size"),
        ambient_temp=("Ambient_Temperature_C", "mean"), belt_temp=("Belt_Temperature_C", "mean"),
        calib_load=("Calib_Load", "mean"),
        calib_load_gt90_pct=("Calib_Load", lambda s: pct(s > CALIB_LOAD_VERY_HIGH)),
        tension_err_gt8_pct=("Tension_Dev_Abs_Pct", lambda s: pct(s > TENSION_ERROR_HIGH_PCT)),
    ).round(1)


def numeric_drift(early, recent, test) -> pd.DataFrame:
    """Mean shift in units of recent-train standard deviation."""
    X_early, X_recent, X_test = (build_features(d) for d in (early, recent, test))
    numeric = [c for c in X_test.columns if c not in config.CATEGORICAL_COLUMNS
               and c != "Month" and not c.startswith("isna_")]
    drift = pd.DataFrame({
        "early_to_recent": [(X_recent[c].mean() - X_early[c].mean()) / X_recent[c].std() for c in numeric],
        "recent_to_test": [(X_test[c].mean() - X_recent[c].mean()) / X_recent[c].std() for c in numeric],
    }, index=numeric)
    return drift.reindex(drift.recent_to_test.abs().sort_values(ascending=False).index).round(3)


def adversarial_auc(recent, test) -> tuple[float, list[str]]:
    """How well a model separates recent-train rows from test rows (0.5 = indistinguishable)."""
    X = pd.concat([build_features(recent), build_features(test)]).reset_index(drop=True)
    X = X.drop(columns=["Month", "Technician_ID"])
    for col in X.columns.intersection(config.CATEGORICAL_COLUMNS):
        X[col] = X[col].astype(str).astype("category")
    is_test = np.r_[np.zeros(len(recent)), np.ones(len(test))]
    model = lgb.LGBMClassifier(n_estimators=200, verbose=-1)
    proba = cross_val_predict(model, X, is_test, cv=StratifiedKFold(5, shuffle=True, random_state=0),
                              method="predict_proba")[:, 1]
    importance = pd.Series(model.fit(X, is_test).booster_.feature_importance("gain"), X.columns)
    return round(roc_auc_score(is_test, proba), 3), importance.nlargest(5).index.tolist()


def main():
    train, test = load_with_features()
    early, recent = train.iloc[:RECENT_ROWS], train.iloc[-RECENT_ROWS:]

    print("1) Monthly defect rate and drivers (train = actual, test = predicted)")
    print("train:\n", monthly_summary(train).to_string())
    print("test:\n", monthly_summary(test).to_string())

    bands = pd.cut(train.Calib_Load, [-1, 30, CALIB_LOAD_HIGH, CALIB_LOAD_VERY_HIGH, np.inf])
    print("\n2) Train defect rate % by calibration load band:\n", train.groupby(bands)[LABEL].agg(pct).to_string())

    print("\n3) Numeric drift (std units), largest recent->test first:\n", numeric_drift(early, recent, test).head(10))

    print("\n4) Missing-value rate % (recent train vs test)")
    for col in config.MISSING_FLAG_COLUMNS:
        print(f"  {col:32s} {pct(recent[col].isna()):5.1f} {pct(test[col].isna()):5.1f}")

    print("\n5) Categories in test never seen in train")
    for col in ["Maintenance_Station", "Tool_ID", "Belt_Supplier", "Belt_Batch_ID"]:
        print(f"  {col}: {sorted(set(test[col]) - set(train[col])) or 'none'}")

    auc, top_features = adversarial_auc(recent, test)
    print(f"\n6) Adversarial AUC recent-train vs test: {auc}  (top separators: {', '.join(top_features)})")


if __name__ == "__main__":
    main()
