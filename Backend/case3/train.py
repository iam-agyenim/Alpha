"""Train the Case 3 belt-defect model and write the submission file.

    python -m case3.train --train <Case_3_Train_Participants.xlsx> --test <case_3_test_inputs.csv> \
        --template <case_3_predictions_template.csv> --out output

Recipe (chosen with the experiments summarised in README.md):
  * cleaning + row-level features from case3.features (no cross-row joins, no absolute date);
  * CatBoost (5 seeds) blended 70/30 with LightGBM (5 seeds);
  * one Yes/No threshold, chosen to maximise the *average* F1 over three validation views:
      1. repeated stratified 5-fold out-of-fold scores on all 10,000 rows,
      2. train on everything except May-Aug 2024, score May-Aug 2024 (an unseen summer),
      3. train on 2024, score Jan-May 2025 (an unseen later period).
    The test set is a later summer (May-Aug 2025), so a threshold that only fits view 1 is too strict.
"""
from __future__ import annotations

import argparse
import json
import time
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold

from .features import CATEGORICAL, ENGINEERED, ID, NUMERIC, TARGET, prepare, target
from .submission import check_submission

warnings.filterwarnings("ignore")

FEATURES = [c for c in CATEGORICAL + NUMERIC + ENGINEERED if c != "Month_Of_Year"]
CATS = [c for c in CATEGORICAL if c in FEATURES]
SEEDS = (0, 1, 2, 3, 4)
CAT_WEIGHT = 0.7
CAT_PARAMS = dict(iterations=1000, learning_rate=0.05, depth=5, l2_leaf_reg=10)
LGB_PARAMS = dict(n_estimators=500, learning_rate=0.03, num_leaves=15, min_child_samples=30, subsample=0.8,
                  subsample_freq=1, colsample_bytree=0.8, reg_lambda=5, verbose=-1)
THRESHOLDS = np.round(np.arange(0.05, 0.501, 0.005), 3)


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


def f1_grid(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    return np.array([f1_score(y, p >= t, zero_division=0) for t in THRESHOLDS])


def validation_views(tr: pd.DataFrame, y: np.ndarray, log) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """(labels, scores) for each validation view; every score comes from a model that never saw that row."""
    views = {}
    oof = np.zeros((2, len(y)))
    for i, (a, b) in enumerate(RepeatedStratifiedKFold(n_splits=5, n_repeats=2, random_state=42).split(tr, y)):
        oof[i // 5, b] = BlendModel().fit(tr.iloc[a], y[a]).predict_proba(tr.iloc[b])
        log(f"  cross-validation fold {i + 1}/10")
    views["cv_oof"] = (y, oof.mean(axis=0))
    d = tr["Maintenance_Date"]
    for name, hold in [("unseen_summer_2024", d.between("2024-05-01", "2024-08-31 23:59:59")),
                       ("unseen_2025", d >= "2025-01-01")]:
        hold = hold.to_numpy()
        p = BlendModel().fit(tr[~hold], y[~hold]).predict_proba(tr[hold])
        views[name] = (y[hold], p)
        log(f"  {name}: done")
    return views


def metrics(y: np.ndarray, p: np.ndarray, thr: float) -> dict:
    pred = p >= thr
    return {"rows": int(len(y)), "defects": int(y.sum()), "f1": round(f1_score(y, pred), 4),
            "precision": round(precision_score(y, pred, zero_division=0), 4),
            "recall": round(recall_score(y, pred), 4), "predicted_yes": int(pred.sum()),
            "best_possible_f1": round(float(f1_grid(y, p).max()), 4),
            "pr_auc": round(average_precision_score(y, p), 4), "roc_auc": round(roc_auc_score(y, p), 4)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", required=True, type=Path)
    ap.add_argument("--test", required=True, type=Path)
    ap.add_argument("--template", required=True, type=Path)
    ap.add_argument("--out", default=Path("output"), type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"[{time.time() - t0:6.0f}s] {msg}", flush=True)

    tr = prepare(pd.read_excel(args.train, sheet_name="Train Data"))
    raw_test = pd.read_csv(args.test, dtype={ID: str})
    te = prepare(raw_test)
    y = target(tr)
    log(f"train {len(tr)} rows ({y.sum()} defects); test {len(te)} rows; {len(FEATURES)} features")

    log("validation")
    views = validation_views(tr, y, log)
    grids = {k: f1_grid(yv, pv) for k, (yv, pv) in views.items()}
    mean_f1 = np.mean(list(grids.values()), axis=0)
    thr = float(THRESHOLDS[int(np.argmax(mean_f1))])
    report = {"threshold": thr, "features": FEATURES, "validation": {k: metrics(*v, thr) for k, v in views.items()}}
    for k, m in report["validation"].items():
        log(f"  {k:20s} F1 {m['f1']:.3f} (P {m['precision']:.2f}, R {m['recall']:.2f}; best possible "
            f"{m['best_possible_f1']:.3f}) PR-AUC {m['pr_auc']:.3f}")
    log(f"threshold {thr} (mean F1 over views {mean_f1.max():.3f})")
    pd.DataFrame({"threshold": THRESHOLDS, **{k: g.round(4) for k, g in grids.items()}, "mean": mean_f1.round(4)}) \
        .to_csv(args.out / "threshold_curve.csv", index=False)

    log("final model on all training rows")
    model = BlendModel().fit(tr, y)
    p_test = model.predict_proba(te)
    model.importance().round(3).rename("importance").to_csv(args.out / "feature_importance.csv",
                                                            index_label="feature")

    template = pd.read_csv(args.template, dtype={ID: str})
    scores = pd.Series(p_test, index=raw_test[ID].to_numpy())
    sub = pd.DataFrame({ID: template[ID],
                        TARGET: np.where(scores.reindex(template[ID]).to_numpy() >= thr, "Yes", "No")})
    sub_path = args.out / "case_3_predictions.csv"
    sub.to_csv(sub_path, index=False, lineterminator="\n", encoding="utf-8")
    pd.DataFrame({ID: raw_test[ID], "Defect_Probability": p_test.round(5),
                  TARGET: np.where(p_test >= thr, "Yes", "No")}).to_csv(args.out / "test_scores.csv", index=False)

    problems = check_submission(sub_path, raw_test[ID])
    report["test"] = {"rows": len(sub), "predicted_yes": int((sub[TARGET] == "Yes").sum()),
                      "predicted_yes_rate": round(float((sub[TARGET] == "Yes").mean()), 4),
                      "mean_probability": round(float(p_test.mean()), 4), "format_problems": problems}
    (args.out / "report.json").write_text(json.dumps(report, indent=2))
    log(f"test: {report['test']['predicted_yes']} of {len(sub)} predicted Yes "
        f"({report['test']['predicted_yes_rate']:.1%}); mean probability {p_test.mean():.3f}")
    log("submission check: " + ("PASSED" if not problems else "FAILED: " + "; ".join(problems)))
    log(f"wrote {sub_path}")


if __name__ == "__main__":
    main()
