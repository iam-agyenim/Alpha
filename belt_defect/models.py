"""Model builders and the final three-model blend."""
import lightgbm as lgb
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Tuned LightGBM settings (see scripts/tune_lightgbm_and_ensembles.py)
LIGHTGBM_PARAMS = dict(
    n_estimators=500, learning_rate=0.03, num_leaves=15, min_child_samples=20,
    subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
    scale_pos_weight=5,  # upweight the rare defect class
    verbose=-1,
)
CATBOOST_PARAMS = dict(
    iterations=800, learning_rate=0.04, depth=5, l2_leaf_reg=3,
    auto_class_weights="SqrtBalanced", verbose=0,
    allow_writing_files=False,  # no catboost_info/ folder
)


def make_lightgbm(seed: int = 0, **overrides) -> lgb.LGBMClassifier:
    """LightGBM with tuned defaults; overrides replace individual params."""
    return lgb.LGBMClassifier(**{**LIGHTGBM_PARAMS, "random_state": seed, **overrides})


def make_catboost(categorical_columns, seed: int = 0) -> CatBoostClassifier:
    """CatBoost using its native categorical handling."""
    return CatBoostClassifier(**CATBOOST_PARAMS, cat_features=categorical_columns, random_seed=seed)


def make_preprocessor(numeric_columns, categorical_columns, scale_numeric: bool = True) -> ColumnTransformer:
    """Median-impute (+ optional scaling) numerics, one-hot encode categoricals."""
    numeric_steps = [SimpleImputer(strategy="median")] + ([StandardScaler()] if scale_numeric else [])
    return ColumnTransformer([
        ("numeric", make_pipeline(*numeric_steps), numeric_columns),
        ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical_columns),
    ])


def make_logistic_regression(numeric_columns, categorical_columns):
    """Regularized, class-balanced logistic regression with preprocessing."""
    return make_pipeline(
        make_preprocessor(numeric_columns, categorical_columns),
        LogisticRegression(C=0.3, class_weight="balanced", max_iter=3000),
    )


def categories_as_strings(features: pd.DataFrame, categorical_columns) -> pd.DataFrame:
    """CatBoost needs string categoricals, not pandas category dtype."""
    features = features.copy()
    for col in categorical_columns:
        features[col] = features[col].astype(str)
    return features


def fit_predict_proba(model, X_train, y_train, X_valid, string_categoricals=None) -> np.ndarray:
    """Fit a model and return defect probabilities for X_valid."""
    if string_categoricals:
        X_train = categories_as_strings(X_train, string_categoricals)
        X_valid = categories_as_strings(X_valid, string_categoricals)
    return model.fit(X_train, y_train).predict_proba(X_valid)[:, 1]


def blend_fit_predict(X_train, y_train, X_valid, seed, numeric_columns, categorical_columns) -> np.ndarray:
    """Final model: equal-weight average of LightGBM, CatBoost and logistic regression probabilities."""
    proba_lightgbm = fit_predict_proba(make_lightgbm(seed), X_train, y_train, X_valid)
    proba_catboost = fit_predict_proba(make_catboost(categorical_columns, seed), X_train, y_train, X_valid,
                                       string_categoricals=categorical_columns)
    proba_logreg = fit_predict_proba(make_logistic_regression(numeric_columns, categorical_columns),
                                     X_train, y_train, X_valid)
    return (proba_lightgbm + proba_catboost + proba_logreg) / 3
