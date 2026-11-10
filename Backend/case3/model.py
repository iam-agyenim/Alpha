"""The Case 3 model: CatBoost x seeds blended with LightGBM x seeds.

Kept in its own module (not train.py) so a saved model unpickles as case3.model.BlendModel wherever it is
loaded, e.g. by the dashboard.
"""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier

from .features import CATEGORICAL, ENGINEERED, NUMERIC

FEATURES = [c for c in CATEGORICAL + NUMERIC + ENGINEERED if c != "Month_Of_Year"]
CATS = [c for c in CATEGORICAL if c in FEATURES]
SEEDS = (0, 1, 2, 3, 4)
CAT_WEIGHT = 0.7
CAT_PARAMS = dict(iterations=1000, learning_rate=0.05, depth=5, l2_leaf_reg=10)
LGB_PARAMS = dict(n_estimators=500, learning_rate=0.03, num_leaves=15, min_child_samples=30, subsample=0.8,
                  subsample_freq=1, colsample_bytree=0.8, reg_lambda=5, verbose=-1)


def _frames(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    xc, xl = df[FEATURES].copy(), df[FEATURES].copy()
    for c in CATS:
        xc[c] = xc[c].astype(str)
        xl[c] = pd.Categorical(xl[c].astype(str))
    return xc, xl


class BlendModel:
    """CatBoost x seeds blended with LightGBM x seeds; predict_proba returns P(defect)."""

    def fit(self, df: pd.DataFrame, y: np.ndarray) -> "BlendModel":
        xc, xl = _frames(df)
        self.lgb_categories = {c: xl[c].cat.categories for c in CATS}
        self.cat = [CatBoostClassifier(verbose=0, cat_features=CATS, random_seed=s, **CAT_PARAMS).fit(xc, y)
                    for s in SEEDS]
        self.lgb = [lgb.LGBMClassifier(random_state=s, **LGB_PARAMS).fit(xl, y) for s in SEEDS]
        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        xc, xl = _frames(df)
        for c in CATS:  # same category codes as at fit time
            xl[c] = pd.Categorical(xl[c].astype(str), categories=self.lgb_categories[c])
        pc = np.mean([m.predict_proba(xc)[:, 1] for m in self.cat], axis=0)
        pl = np.mean([m.predict_proba(xl)[:, 1] for m in self.lgb], axis=0)
        return CAT_WEIGHT * pc + (1 - CAT_WEIGHT) * pl

    def importance(self) -> pd.Series:
        imp = np.mean([m.get_feature_importance() for m in self.cat], axis=0)
        return pd.Series(imp, FEATURES).sort_values(ascending=False)
