"""Pre-job defect risk models.

Only information known BEFORE the job is used as input. Belt condition,
temperature and vibration are measured at the same inspection that finds the
defect, so using them would be predicting the answer from the answer.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import LeaveOneOut, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier

from .data import FACTOR_LABELS, LEADING, SYMPTOMS
from .stats import bayes_rates

PRE_JOB_FEATURES = list(LEADING)
SYMPTOM_FEATURES = list(SYMPTOMS)

FEATURE_REASONS = {
    "Tool_ID": "Known when the job card is opened (which tool is issued).",
    "Tool_Status": "Calibration status is on the tool's tag before the job starts.",
    "Maintenance_Station": "Known when the job is planned.",
    "Month": "Known when the job is planned.",
    "Belt_Condition": "EXCLUDED: recorded at the same inspection that finds the defect (symptom).",
    "Belt_Temperature": "EXCLUDED: measured at the same inspection that finds the defect (symptom).",
    "Belt_Vibration": "EXCLUDED: measured at the same inspection that finds the defect (symptom).",
    "Record_ID": "EXCLUDED: an identifier, carries no information about risk.",
    "Aircraft_ID": "EXCLUDED: each aircraft appears once, so it cannot generalise.",
}


def features_for(df: pd.DataFrame, kind: str = "pre_job") -> list[str]:
    cols = PRE_JOB_FEATURES if kind == "pre_job" else SYMPTOM_FEATURES
    return [c for c in cols if c in df.columns and df[c].nunique() > 1]


def _encoder(features):
    return ColumnTransformer([("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False), features)])


def logistic_pipeline(features, C: float = 1.0) -> Pipeline:
    # L2-penalised (sklearn default). The penalty keeps coefficients finite under perfect separation.
    return Pipeline([("enc", _encoder(features)),
                     ("clf", LogisticRegression(C=C, class_weight="balanced", max_iter=5000))])


def tree_pipeline(features) -> Pipeline:
    return Pipeline([("enc", _encoder(features)),
                     ("clf", DecisionTreeClassifier(max_depth=2, random_state=0))])


def _onehot_names(pipe: Pipeline, features) -> list[tuple[str, str]]:
    enc = pipe.named_steps["enc"].named_transformers_["oh"]
    return [(f, str(lvl)) for f, cats in zip(features, enc.categories_) for lvl in cats]


# ----------------------------------------------------------------------------
# Decision tree -> plain English rule
# ----------------------------------------------------------------------------

def fit_tree(df: pd.DataFrame, features=None) -> dict:
    features = features or features_for(df)
    pipe = tree_pipeline(features).fit(df[features], df["defect"])
    names = _onehot_names(pipe, features)
    t = pipe.named_steps["clf"].tree_
    rules, nodes, edges = [], [], []

    # Count jobs and defects reaching each node directly from the training data.
    path = pipe.named_steps["clf"].decision_path(pipe.named_steps["enc"].transform(df[features]))
    node_n = np.asarray(path.sum(axis=0)).ravel()
    node_d = np.asarray(path.T @ df["defect"].to_numpy()).ravel()

    def leaf_text(node):
        return int(node_n[node]), int(node_d[node])

    def walk(node, conds):
        n, d = leaf_text(node)
        if t.children_left[node] == -1:
            pred = "defect" if d / max(n, 1) >= 0.5 else "no defect"
            rules.append({"conditions": conds or ["(all jobs)"], "jobs": n, "defects": d, "prediction": pred})
            nodes.append((node, f"{d} of {n} jobs had a defect\\n→ predict {pred}", pred))
            return
        f, lvl = names[t.feature[node]]
        label = FACTOR_LABELS.get(f, f)
        nodes.append((node, f"{label} = {lvl}?\\n({d} of {n} defects)", "split"))
        left, right = t.children_left[node], t.children_right[node]
        edges.append((node, right, "yes"))
        edges.append((node, left, "no"))
        walk(right, conds + [f"{label} is '{lvl}'"])
        walk(left, conds + [f"{label} is not '{lvl}'"])

    walk(0, [])
    english = [f"IF {' AND '.join(r['conditions'])} THEN predict {r['prediction'].upper()} "
               f"({r['defects']} of {r['jobs']} past jobs had a defect)" for r in rules]
    colours = {"defect": "#d03b3b", "no defect": "#0ca30c", "split": "#1F3A5F"}
    dot = ["digraph tree {", 'node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=14 fontcolor=white];',
           'edge [fontname="Helvetica" fontsize=13];']
    for nid, text, kind in nodes:
        dot.append(f'n{nid} [label="{text}" fillcolor="{colours[kind]}"];')
    for a, b, lab in edges:
        dot.append(f'n{a} -> n{b} [label="{lab}"];')
    dot.append("}")
    return {"pipeline": pipe, "features": features, "rules": rules, "english": english, "dot": "\n".join(dot)}


# ----------------------------------------------------------------------------
# Logistic regression (L2) + Firth penalised logistic regression
# ----------------------------------------------------------------------------

def fit_logistic(df: pd.DataFrame, features=None, C: float = 1.0) -> dict:
    features = features or features_for(df)
    pipe = logistic_pipeline(features, C).fit(df[features], df["defect"])
    names = _onehot_names(pipe, features)
    coefs = pipe.named_steps["clf"].coef_[0]
    coef_df = pd.DataFrame({"factor": [FACTOR_LABELS.get(f, f) for f, _ in names], "level": [l for _, l in names],
                            "coefficient": coefs, "odds_multiplier": np.exp(coefs)})
    coef_df = coef_df.reindex(coef_df["coefficient"].abs().sort_values(ascending=False).index).reset_index(drop=True)
    df_out = df.copy()
    df_out["risk"] = pipe.predict_proba(df[features])[:, 1]
    return {"pipeline": pipe, "features": features, "coefficients": coef_df, "fitted": df_out}


def _design(df: pd.DataFrame, features) -> tuple[np.ndarray, list[str]]:
    """Dummy coding (drop first) + intercept, dropping columns that are linear combinations of earlier ones."""
    X = pd.get_dummies(df[features].astype(str), drop_first=True, dtype=float)
    cols, mats = ["(intercept)"], [np.ones(len(df))]
    for c in X.columns:
        cand = np.column_stack(mats + [X[c].to_numpy()])
        if np.linalg.matrix_rank(cand) == cand.shape[1]:
            mats.append(X[c].to_numpy())
            cols.append(c)
    return np.column_stack(mats), cols


def firth_logistic(X: np.ndarray, y: np.ndarray, max_iter: int = 200, tol: float = 1e-8) -> dict:
    """Firth (1993) bias-reduced logistic regression via Newton-Raphson with step halving."""
    beta = np.zeros(X.shape[1])

    def penalised_ll(b):
        p = 1 / (1 + np.exp(-(X @ b)))
        p = np.clip(p, 1e-12, 1 - 1e-12)
        info = X.T @ (X * (p * (1 - p))[:, None])
        sign, logdet = np.linalg.slogdet(info)
        return np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)) + 0.5 * logdet, p, info

    ll, p, info = penalised_ll(beta)
    converged = False
    for _ in range(max_iter):
        W = p * (1 - p)
        inv = np.linalg.pinv(info)
        h = np.einsum("ij,jk,ik->i", X * np.sqrt(W)[:, None], inv, X * np.sqrt(W)[:, None])
        score = X.T @ (y - p + h * (0.5 - p))
        step = inv @ score
        t = 1.0
        while t > 1e-6:
            new = beta + t * step
            ll_new, p_new, info_new = penalised_ll(new)
            if ll_new >= ll - 1e-12:
                break
            t /= 2
        beta, ll, p, info = new, ll_new, p_new, info_new
        if np.max(np.abs(t * step)) < tol:
            converged = True
            break
    return {"beta": beta, "converged": converged, "fitted": p}


def fit_firth(df: pd.DataFrame, features=None) -> dict:
    features = features or features_for(df)
    X, cols = _design(df, features)
    res = firth_logistic(X, df["defect"].to_numpy(float))
    coefs = pd.DataFrame({"term": cols, "coefficient": res["beta"], "odds_multiplier": np.exp(res["beta"])})
    return {"coefficients": coefs, "converged": res["converged"], "fitted": res["fitted"], "columns": cols}


def separation_check(df: pd.DataFrame, features=None) -> list[str]:
    """Factor levels whose jobs are all defects or all clean (perfect/quasi separation)."""
    features = features or features_for(df)
    out = []
    for f in features:
        g = df.groupby(f)["defect"].agg(["mean", "size"])
        for lvl, r in g.iterrows():
            if r["mean"] in (0.0, 1.0) and r["size"] >= 3 and 0 < df["defect"].mean() < 1:
                if (df[f] == lvl).sum() and abs(r["mean"] - df.loc[df[f] != lvl, "defect"].mean()) == 1.0:
                    out.append(f"{FACTOR_LABELS.get(f, f)} = {lvl}")
    return out


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------

def _metrics(y, prob, threshold=0.5) -> dict:
    pred = (prob >= threshold).astype(int)
    cm = confusion_matrix(y, pred, labels=[0, 1])
    auc = roc_auc_score(y, prob) if len(set(y)) == 2 else float("nan")
    return {"auc": float(auc), "recall": float(recall_score(y, pred, zero_division=0)),
            "precision": float(precision_score(y, pred, zero_division=0)),
            "confusion": cm, "tn": int(cm[0, 0]), "fp": int(cm[0, 1]), "fn": int(cm[1, 0]), "tp": int(cm[1, 1])}


def validate(df: pd.DataFrame, make_pipeline, features) -> dict:
    y = df["defect"].to_numpy()
    n_pos, n_neg = int(y.sum()), int(len(y) - y.sum())
    out = {"n": len(y), "defects": n_pos, "warnings": [], "loo": None, "kfold": None}
    if n_pos < 2 or n_neg < 2 or not features:
        out["warnings"].append("Not enough defects and non-defects to validate a model.")
        return out
    prob = cross_val_predict(make_pipeline(features), df[features], y, cv=LeaveOneOut(), method="predict_proba")[:, 1]
    out["loo"] = _metrics(y, prob)
    out["loo_prob"] = prob
    if min(n_pos, n_neg) >= 5:
        k = min(5, n_pos, n_neg)
        cv = StratifiedKFold(n_splits=k, shuffle=True, random_state=0)
        prob_k = cross_val_predict(make_pipeline(features), df[features], y, cv=cv, method="predict_proba")[:, 1]
        out["kfold"] = _metrics(y, prob_k) | {"k": k}
    if n_pos < 30:
        out["warnings"].append(f"Only {n_pos} defects: these scores are unstable and a few new records could change them a lot.")
    sep = separation_check(df, features)
    if sep:
        out["warnings"].append("Perfect separation in this sample (" + "; ".join(sep) + "): a perfect score here "
                               "shows the pattern is clean in these 30 jobs, not that the model will be perfect on new jobs.")
    return out


def validate_pre_job(df: pd.DataFrame) -> dict:
    feats = features_for(df)
    return {"logistic": validate(df, logistic_pipeline, feats), "tree": validate(df, tree_pipeline, feats),
            "features": feats}


def leakage_demo(df: pd.DataFrame) -> dict | None:
    feats = features_for(df, "symptoms")
    if not feats:
        return None
    return {"features": feats, "validation": validate(df, logistic_pipeline, feats),
            "explanation": ("This model scores just as well, but it is useless: belt condition, temperature and "
                            "vibration are recorded at the same inspection that finds the defect. It predicts the "
                            "answer from the answer and gives no warning before the job starts.")}


# ----------------------------------------------------------------------------
# Pre-job risk checker
# ----------------------------------------------------------------------------

def risk_band(prob: float, high: float = 0.5, medium: float = 0.2) -> str:
    return "High" if prob >= high else "Medium" if prob >= medium else "Low"


def check_job(df: pd.DataFrame, model: dict, job: dict, high=0.5, medium=0.2) -> dict:
    feats = model["features"]
    row = pd.DataFrame([{f: job.get(f) for f in feats}])
    prob = float(model["pipeline"].predict_proba(row)[:, 1][0])
    band = risk_band(prob, high, medium)
    # Bayesian evidence for the matching Tool_Status group
    b = bayes_rates(df, "Tool_Status").set_index("level")
    status = job.get("Tool_Status")
    bayes = b.loc[status].to_dict() if status in b.index else None
    # Main reason: for raised risk, the input whose past defect rate is furthest ABOVE the fleet rate;
    # for low risk, the one furthest BELOW it.
    fleet = df["defect"].mean()
    sign = -1.0 if band == "Low" else 1.0
    best, best_key = None, (1e-12, 0)
    for f in feats:
        sub = df[df[f] == job.get(f)]
        if len(sub) == 0:
            continue
        key = (round(sign * (sub["defect"].mean() - fleet), 9), len(sub))  # ties -> more evidence wins
        if key > best_key:
            best, best_key = (f, job.get(f), int(sub["defect"].sum()), len(sub)), key
    if best:
        f, lvl, d, n = best
        reason = f"{FACTOR_LABELS[f]} '{lvl}' had a defect in {d} of {n} past jobs (fleet average {fleet:.0%})."
    else:
        reason = f"None of the selected options differs from the fleet average defect rate ({fleet:.0%})."
    if band == "High":
        if best and best[0] in ("Tool_ID", "Tool_Status"):
            rec = "Stop: swap to a tool in Normal (calibrated) status before starting, and quarantine this tool."
        else:
            rec = "Stop: review the job set-up with a supervisor before starting."
    elif band == "Medium":
        rec = "Proceed with care: verify tool calibration tag and re-check belt tension after the job."
    else:
        rec = "Proceed with the standard procedure."
    return {"probability": prob, "band": band, "reason": reason, "recommendation": rec, "bayes": bayes}
