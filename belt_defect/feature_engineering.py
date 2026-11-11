"""Build model features from cleaned data.

Every feature comes from the row itself (no joins across rows), as the problem requires.
The one exception is the median used to fill missing calibration values.
"""
import pandas as pd

from .config import CATEGORICAL_COLUMNS, DATE_COLUMN, EXCLUDED_FEATURES, MISSING_FLAG_COLUMNS, NUMERIC_COLUMNS


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return all candidate features (column order matters for reproducibility)."""
    features = df[NUMERIC_COLUMNS].copy()

    # Tension error: measured vs target, raw and as a %
    tension_error = df.Belt_Measured_Tension_N - df.Belt_Target_Tension_N
    features["Tension_Dev_N"] = tension_error
    features["Tension_Dev_Abs"] = tension_error.abs()
    features["Tension_Dev_Pct"] = tension_error / df.Belt_Target_Tension_N * 100
    features["Tension_Dev_Abs_Pct"] = features["Tension_Dev_Pct"].abs()

    # Calibration load: days since calibration x uses since calibration (strong defect driver)
    days_since_cal = df.Days_Since_Tool_Calibration.fillna(df.Days_Since_Tool_Calibration.median())
    uses_since_cal = df.Tool_Uses_Since_Calibration.fillna(df.Tool_Uses_Since_Calibration.median())
    features["Calib_Load"] = days_since_cal * uses_since_cal / 1000

    # Usage and heat ratios
    features["Hours_per_Cycle"] = df.Belt_Age_Hours / (df.Cycles_Since_Belt_Install + 1)
    features["Temp_over_Ambient"] = df.Belt_Temperature_C - df.Ambient_Temperature_C
    features["High_Load_Share"] = df.High_Load_Hours_Last_30_Days / df.Operating_Hours_Last_30_Days
    features["Month"] = df[DATE_COLUMN].dt.month

    # Missing-value flags
    for col in MISSING_FLAG_COLUMNS:
        features[f"isna_{col}"] = df[col].isna().astype(int)

    for col in CATEGORICAL_COLUMNS:
        features[col] = df[col].astype("category")
    return features


def select_model_features(features: pd.DataFrame, excluded=EXCLUDED_FEATURES) -> pd.DataFrame:
    """Drop excluded features."""
    return features[[c for c in features.columns if c not in excluded]]


def split_column_types(features: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return (numeric_columns, categorical_columns) present in a feature table."""
    categorical = [c for c in features.columns if c in CATEGORICAL_COLUMNS]
    numeric = [c for c in features.columns if c not in CATEGORICAL_COLUMNS]
    return numeric, categorical


def align_categories(train_features: pd.DataFrame, test_features: pd.DataFrame, categorical_columns):
    """Give train and test the same category set so unseen test labels are handled."""
    train_features, test_features = train_features.copy(), test_features.copy()
    for col in categorical_columns:
        shared = sorted(set(train_features[col].astype(str)) | set(test_features[col].astype(str)))
        train_features[col] = pd.Categorical(train_features[col].astype(str), categories=shared)
        test_features[col] = pd.Categorical(test_features[col].astype(str), categories=shared)
    return train_features, test_features
