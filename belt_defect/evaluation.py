"""Cross-validation, temporal holdout and F1 threshold selection."""
from typing import Callable, NamedTuple

import numpy as np
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold

from .config import EXPERIMENT_SEEDS, N_FOLDS, TEMPORAL_TRAIN_FRACTION

# fit_predict(X_train, y_train, X_valid, seed) -> defect probabilities for X_valid
FitPredict = Callable[..., np.ndarray]


def candidate_thresholds(proba: np.ndarray, n_points: int) -> np.ndarray:
    """Thresholds at the 80th-99.9th percentiles of the scores (defects are ~3% of rows)."""
    return np.unique(np.quantile(proba, np.linspace(0.80, 0.999, n_points)))


def best_f1_threshold(y_true, proba, n_points: int = 400) -> tuple[float, float]:
    """Return (threshold, F1) that maximizes F1."""
    thresholds = candidate_thresholds(proba, n_points)
    f1_scores = [f1_score(y_true, proba >= t) for t in thresholds]
    best = int(np.argmax(f1_scores))
    return thresholds[best], f1_scores[best]


def recall_leaning_threshold(y_true, proba, tolerance: float, n_points: int = 500) -> tuple[float, float, float]:
    """Lowest threshold whose F1 is within `tolerance` of the best.

    Returns (chosen_threshold, best_threshold, best_f1).
    """
    thresholds = candidate_thresholds(proba, n_points)
    f1_scores = np.array([f1_score(y_true, proba >= t) for t in thresholds])
    near_best = np.where(f1_scores >= f1_scores.max() - tolerance)[0]
    return float(thresholds[near_best.min()]), float(thresholds[f1_scores.argmax()]), float(f1_scores.max())


def out_of_fold_proba(fit_predict: FitPredict, X, y, seeds, n_folds: int = N_FOLDS) -> np.ndarray:
    """Stratified K-fold out-of-fold probabilities, averaged over repeats (one per seed)."""
    proba_per_seed = np.zeros((len(seeds), len(y)))
    for i, seed in enumerate(seeds):
        folds = StratifiedKFold(n_folds, shuffle=True, random_state=seed)
        for train_idx, valid_idx in folds.split(X, y):
            proba_per_seed[i, valid_idx] = fit_predict(X.iloc[train_idx], y[train_idx], X.iloc[valid_idx], seed)
    return proba_per_seed.mean(axis=0)


class ValidationProba(NamedTuple):
    """Probabilities from both validation schemes."""
    cv: np.ndarray               # out-of-fold, all rows
    early_cv: np.ndarray         # out-of-fold within the early (training) part, for picking its threshold
    late_holdout: np.ndarray     # late part, predicted by a model trained on the early part


def temporal_split_index(n_rows: int) -> int:
    """Row index where the late holdout starts (data must be sorted by date)."""
    return int(n_rows * TEMPORAL_TRAIN_FRACTION)


def run_validation_schemes(fit_predict: FitPredict, X, y, cv_seeds=EXPERIMENT_SEEDS) -> ValidationProba:
    """A) repeated stratified CV on all rows; B) train on early rows, predict late rows."""
    split = temporal_split_index(len(y))
    X_early, y_early = X.iloc[:split], y[:split]
    return ValidationProba(
        cv=out_of_fold_proba(fit_predict, X, y, cv_seeds),
        early_cv=out_of_fold_proba(fit_predict, X_early, y_early, seeds=(0,)),
        late_holdout=fit_predict(X_early, y_early, X.iloc[split:], 0),
    )


def score_validation(name: str, y, proba: ValidationProba) -> dict:
    """F1 / precision / recall / PR-AUC for both schemes.

    The temporal threshold comes from early-period CV only, so the late period stays unseen.
    """
    cv_threshold, cv_f1 = best_f1_threshold(y, proba.cv)
    cv_pred = proba.cv >= cv_threshold

    split = temporal_split_index(len(y))
    early_threshold, _ = best_f1_threshold(y[:split], proba.early_cv)
    y_late = y[split:]
    late_pred = proba.late_holdout >= early_threshold

    return dict(
        Model=name,
        CV_F1=cv_f1,
        CV_Precision=precision_score(y, cv_pred),
        CV_Recall=recall_score(y, cv_pred),
        CV_PR_AUC=average_precision_score(y, proba.cv),
        Time_F1=f1_score(y_late, late_pred),
        Time_Precision=precision_score(y_late, late_pred, zero_division=0),
        Time_Recall=recall_score(y_late, late_pred),
        Time_PR_AUC=average_precision_score(y_late, proba.late_holdout),
        Time_Best_F1=best_f1_threshold(y_late, proba.late_holdout)[1],  # ceiling if threshold were perfect
    )
