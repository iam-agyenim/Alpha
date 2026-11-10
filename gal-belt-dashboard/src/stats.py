"""Statistical analysis of belt defects. Pure functions: DataFrame in, tidy results out."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats as sps
from statsmodels.stats.multitest import multipletests

from .data import CAL_STATUS, FACTOR_LABELS, LEADING, NORMAL_STATUS, SYMPTOMS, month_order

SEED = 42
ALPHA = 0.05


def _fmt_p(p: float) -> str:
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "n/a"
    if p < 0.0001:
        return f"{p:.1e}"
    return f"{p:.3f}" if p < 0.1 else f"{p:.2f}"


fmt_p = _fmt_p


def factors_present(df: pd.DataFrame, include_symptoms: bool = True) -> list[str]:
    cols = LEADING + (SYMPTOMS if include_symptoms else [])
    return [c for c in cols if c in df.columns]


def levels(df: pd.DataFrame, factor: str) -> list[str]:
    vals = df[factor].dropna().unique().tolist()
    return month_order(vals) if factor == "Month" else sorted(vals)


# ----------------------------------------------------------------------------
# A. Association
# ----------------------------------------------------------------------------

def rates_by_factor(df: pd.DataFrame, factor: str) -> pd.DataFrame:
    """Jobs, defects, rate, and rate in all other jobs, per level of one factor."""
    total_n, total_d = len(df), int(df["defect"].sum())
    rows = []
    for lvl in levels(df, factor):
        sub = df[df[factor] == lvl]
        n, d = len(sub), int(sub["defect"].sum())
        n_rest, d_rest = total_n - n, total_d - d
        rate = d / n if n else float("nan")
        rate_rest = d_rest / n_rest if n_rest else float("nan")
        if n_rest == 0 or (rate_rest == 0 and rate == 0):
            rr = float("nan")
        elif rate_rest == 0:
            rr = float("inf")
        else:
            rr = rate / rate_rest
        rows.append({"factor": factor, "level": lvl, "jobs": n, "defects": d, "rate": rate,
                     "jobs_rest": n_rest, "defects_rest": d_rest, "rate_rest": rate_rest, "relative_risk": rr})
    return pd.DataFrame(rows)


def fisher_level_tests(df: pd.DataFrame, factors: list[str] | None = None) -> pd.DataFrame:
    """Fisher's exact test (2x2) for each level vs the rest, with Benjamini-Hochberg q-values."""
    factors = factors or factors_present(df)
    frames = []
    for f in factors:
        r = rates_by_factor(df, f)
        if len(r) < 2:
            continue
        frames.append(r)
    if not frames:
        return pd.DataFrame(columns=["factor", "level", "p_fisher", "q_bh"])
    out = pd.concat(frames, ignore_index=True)
    ps = []
    for _, row in out.iterrows():
        table = [[row.defects, row.jobs - row.defects], [row.defects_rest, row.jobs_rest - row.defects_rest]]
        ps.append(float(sps.fisher_exact(table, alternative="two-sided").pvalue))
    out["p_fisher"] = ps
    out["q_bh"] = multipletests(ps, method="fdr_bh")[1] if ps else []
    out["role"] = np.where(out["factor"].isin(SYMPTOMS), "Symptom (not a cause)", "Known before job")
    return out


def _permutation_chi2_p(df: pd.DataFrame, factor: str, observed: float, n_perm: int = 20000) -> float:
    """Monte Carlo exact p for an r x 2 table (Freeman-Halton style), fixed seed."""
    rng = np.random.default_rng(SEED)
    codes = pd.Categorical(df[factor]).codes
    y = df["defect"].to_numpy()
    k = codes.max() + 1
    n_i = np.bincount(codes, minlength=k)
    p = y.mean()
    exp1, exp0 = n_i * p, n_i * (1 - p)
    hits = 0
    for _ in range(n_perm):
        yp = rng.permutation(y)
        d_i = np.bincount(codes, weights=yp, minlength=k)
        chi = np.sum((d_i - exp1) ** 2 / exp1) + np.sum(((n_i - d_i) - exp0) ** 2 / exp0)
        hits += chi >= observed - 1e-9
    return (hits + 1) / (n_perm + 1)


def chi_square_factor(df: pd.DataFrame, factor: str) -> dict:
    """Chi-square test of independence + Cramér's V. Falls back to an exact test on small counts."""
    table = pd.crosstab(df[factor], df["defect"]).reindex(columns=[0, 1], fill_value=0)
    n = int(table.to_numpy().sum())
    res = {"factor": factor, "levels": len(table), "n": n, "chi2": float("nan"), "dof": 0,
           "p_chi2": float("nan"), "cramers_v": float("nan"), "min_expected": float("nan"),
           "p_exact": float("nan"), "exact_method": "", "p_used": float("nan"), "note": ""}
    if len(table) < 2:
        res["note"] = "Only one group: nothing to compare."
        return res
    if table[1].sum() == 0 or table[0].sum() == 0:
        res.update(p_chi2=1.0, p_used=1.0, cramers_v=0.0,
                   note="All jobs have the same outcome, so this factor cannot be associated with defects.")
        return res
    chi2, p, dof, expected = sps.chi2_contingency(table.to_numpy(), correction=False)
    v = math.sqrt(chi2 / (n * (min(table.shape) - 1)))
    res.update(chi2=float(chi2), dof=int(dof), p_chi2=float(p), cramers_v=float(v),
               min_expected=float(expected.min()), p_used=float(p))
    if expected.min() < 5:
        if table.shape == (2, 2):
            pe = float(sps.fisher_exact(table.to_numpy()).pvalue)
            method = "Fisher's exact test"
        else:
            pe = _permutation_chi2_p(df, factor, chi2)
            method = "exact permutation test (Fisher-Freeman-Halton, 20,000 shuffles)"
        res.update(p_exact=pe, exact_method=method, p_used=pe,
                   note=f"Some expected counts are below 5 (min {expected.min():.1f}), so the {method} p-value is used.")
    return res


def association_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = [chi_square_factor(df, f) for f in factors_present(df)]
    out = pd.DataFrame(rows)
    out["role"] = np.where(out["factor"].isin(SYMPTOMS), "Symptom (not a cause)", "Known before job")
    return out


def factor_ranking(df: pd.DataFrame) -> pd.DataFrame:
    """One row per factor level, ranked by BH q-value then relative risk."""
    fl = fisher_level_tests(df)
    if fl.empty:
        return fl
    v = association_table(df).set_index("factor")["cramers_v"]
    fl["cramers_v"] = fl["factor"].map(v)
    fl["rr_sort"] = fl["relative_risk"].replace(np.inf, 1e12).fillna(0)
    return fl.sort_values(["q_bh", "rr_sort"], ascending=[True, False]).drop(columns="rr_sort").reset_index(drop=True)


def bayes_rates(df: pd.DataFrame, factor: str, prior=(1.0, 1.0), n_draws: int = 40000) -> pd.DataFrame:
    """Beta-binomial posterior per group: mean, 90% credible interval, P(group rate > rest rate)."""
    rng = np.random.default_rng(SEED)
    a0, b0 = prior
    rows = []
    for _, r in rates_by_factor(df, factor).iterrows():
        a, b = a0 + r.defects, b0 + r.jobs - r.defects
        ar, br = a0 + r.defects_rest, b0 + r.jobs_rest - r.defects_rest
        draws = rng.beta(a, b, n_draws)
        draws_rest = rng.beta(ar, br, n_draws)
        rows.append({"factor": factor, "level": r.level, "jobs": r.jobs, "defects": r.defects,
                     "post_mean": a / (a + b), "ci_low": sps.beta.ppf(0.05, a, b),
                     "ci_high": sps.beta.ppf(0.95, a, b), "p_higher_than_rest": float((draws > draws_rest).mean())})
    return pd.DataFrame(rows)


def bayes_overall(df: pd.DataFrame, prior=(1.0, 1.0)) -> dict:
    a = prior[0] + df["defect"].sum()
    b = prior[1] + len(df) - df["defect"].sum()
    return {"post_mean": a / (a + b), "ci_low": sps.beta.ppf(0.05, a, b), "ci_high": sps.beta.ppf(0.95, a, b)}


def pareto(df: pd.DataFrame, factor: str = "Tool_ID") -> pd.DataFrame:
    r = rates_by_factor(df, factor)[["level", "jobs", "defects"]].sort_values(
        ["defects", "level"], ascending=[False, True]).reset_index(drop=True)
    total = r["defects"].sum()
    r["cum_defects"] = r["defects"].cumsum()
    r["cum_pct"] = r["cum_defects"] / total * 100 if total else 0.0
    return r


# ----------------------------------------------------------------------------
# Top suspect factor (computed, never hardcoded)
# ----------------------------------------------------------------------------

def detect_top_factor(df: pd.DataFrame) -> dict | None:
    """The pre-job factor level most strongly linked to defects (lowest BH q, then highest relative risk)."""
    if df["defect"].sum() == 0:
        return None
    fl = fisher_level_tests(df, [f for f in LEADING if f in df.columns])
    fl = fl[fl["rate"] > fl["rate_rest"]]
    if fl.empty:
        return None
    fl = fl.assign(rr_sort=fl["relative_risk"].replace(np.inf, 1e12).fillna(0),
                   # Prefer the more specific factor (tool) over its status on an exact tie.
                   pref=fl["factor"].map({f: i for i, f in enumerate(LEADING)}))
    best = fl.sort_values(["q_bh", "rr_sort", "pref"], ascending=[True, False, True]).iloc[0]
    mask = df[best.factor] == best.level
    confounded = []
    for f in LEADING:
        if f == best.factor or f not in df.columns:
            continue
        for lvl in df[f].unique():
            if ((df[f] == lvl) == mask).all():
                confounded.append({"factor": f, "level": lvl})
    return {
        "factor": best.factor, "level": best.level, "label": FACTOR_LABELS[best.factor],
        "jobs": int(best.jobs), "defects": int(best.defects), "rate": float(best.rate),
        "jobs_rest": int(best.jobs_rest), "defects_rest": int(best.defects_rest), "rate_rest": float(best.rate_rest),
        "relative_risk": float(best.relative_risk), "p_fisher": float(best.p_fisher), "q_bh": float(best.q_bh),
        "significant": bool(best.q_bh < ALPHA),
        "share_of_defects": float(best.defects / df["defect"].sum()),
        "confounded_with": confounded,
    }


def suspect_mask(df: pd.DataFrame, top: dict | None) -> pd.Series:
    if top is None:
        return pd.Series(False, index=df.index)
    return df[top["factor"]] == top["level"]


def suspect_name(top: dict | None) -> str:
    if top is None:
        return "none"
    extra = "".join(f" ({c['level'].lower()})" if c["factor"] == "Tool_Status" else f" / {c['level']}"
                    for c in top["confounded_with"])
    return f"{top['level']}{extra}"


def rest_label(top: dict | None) -> str:
    """How to describe 'all other jobs' for the suspect factor, e.g. 'with other tools'."""
    if top is None:
        return "in other jobs"
    return {"Tool_ID": "with other tools", "Tool_Status": "with tools in other statuses",
            "Maintenance_Station": "at other stations", "Month": "in other months"}[top["factor"]]


def alert_text(df: pd.DataFrame, top: dict | None) -> str:
    n, d = len(df), int(df["defect"].sum())
    head = f"{d} of {n} jobs ({d / n:.0%}) found a belt defect." if n else "No records."
    if top is None:
        return head + " No pre-job factor stands out."
    who = suspect_name(top)
    share = "Every defect" if top["defects"] == d else f"{top['defects']} of {d} defects"
    body = (f" {share} involved {who}: {top['defects']} of {top['jobs']} jobs vs "
            f"{top['defects_rest']} of {top['jobs_rest']} {rest_label(top)} (Fisher p ≈ {top['p_fisher']:.2g}).")
    if not top["significant"]:
        body += " This difference is not statistically significant after correction."
    return head + body


# ----------------------------------------------------------------------------
# B. Time
# ----------------------------------------------------------------------------

def monthly_summary(df: pd.DataFrame, top: dict | None = None) -> pd.DataFrame:
    sus = suspect_mask(df, top)
    rows = []
    for m in month_order(df["Month"].unique()):
        sel = df["Month"] == m
        rows.append({"month": m, "jobs": int(sel.sum()), "defects": int(df.loc[sel, "defect"].sum()),
                     "rate": float(df.loc[sel, "defect"].mean()), "suspect_jobs": int((sel & sus).sum()),
                     "suspect_defects": int(df.loc[sel & sus, "defect"].sum())})
    return pd.DataFrame(rows)


def p_chart(df: pd.DataFrame) -> dict:
    m = monthly_summary(df)
    p = df["defect"].mean()
    se = np.sqrt(p * (1 - p) / m["jobs"])
    m["centre"] = p
    m["ucl"] = np.minimum(1.0, p + 3 * se)
    m["lcl"] = np.maximum(0.0, p - 3 * se)
    m["out_of_control"] = (m["rate"] > m["ucl"]) | (m["rate"] < m["lcl"])
    out = m.loc[m["out_of_control"], "month"].tolist()
    text = (f"No month falls outside the control limits: month-to-month variation is consistent with chance."
            if not out else f"Out of control: {', '.join(out)}. Investigate what changed in those months.")
    return {"table": m, "centre": float(p), "out_months": out, "interpretation": text}


def cochran_armitage(df: pd.DataFrame) -> dict:
    """Two-sided Cochran-Armitage test for a linear trend in defect rate across ordered months."""
    m = monthly_summary(df)
    if len(m) < 2:
        return {"z": float("nan"), "p": float("nan"), "interpretation": "Needs at least two months to test a trend."}
    n_i, x_i = m["jobs"].to_numpy(float), m["defects"].to_numpy(float)
    t = np.arange(len(m), dtype=float)
    N, p = n_i.sum(), x_i.sum() / n_i.sum()
    T = np.sum(t * (x_i - n_i * p))
    var = p * (1 - p) * (np.sum(n_i * t ** 2) - np.sum(n_i * t) ** 2 / N)
    if var <= 0:
        return {"z": 0.0, "p": 1.0, "interpretation": "No variation in defects, so there is no trend to test."}
    z = T / math.sqrt(var)
    pv = 2 * sps.norm.sf(abs(z))
    direction = "rising" if z > 0 else "falling"
    if pv < ALPHA:
        text = f"Defect rate shows a statistically significant {direction} trend over the months (p = {_fmt_p(pv)})."
    else:
        text = (f"No statistically significant trend (p = {_fmt_p(pv)}): the change between months is "
                f"within what chance alone would produce with this many jobs.")
    return {"z": float(z), "p": float(pv), "interpretation": text}


# ----------------------------------------------------------------------------
# C. Causation vs correlation
# ----------------------------------------------------------------------------

def stratify(df: pd.DataFrame, factor: str, by: str) -> dict:
    """Defect rates of `factor` within each level of `by`, and whether its effect survives."""
    rows, verdicts = [], []
    for s in levels(df, by):
        sub = df[df[by] == s]
        for lvl in levels(sub, factor):
            g = sub[sub[factor] == lvl]
            rows.append({by: s, factor: lvl, "jobs": len(g), "defects": int(g["defect"].sum()),
                         "rate": g["defect"].mean()})
        rates = sub.groupby(factor)["defect"].mean()
        spread = float(rates.max() - rates.min()) if len(rates) else 0.0
        p = chi_square_factor(sub, factor)["p_used"] if len(rates) > 1 else float("nan")
        p = 1.0 if (isinstance(p, float) and math.isnan(p)) else p
        verdicts.append({by: s, "jobs": len(sub), "rate_spread": spread, "p": p,
                         "effect": bool(spread > 0 and p < ALPHA)})
    table = pd.DataFrame(rows)
    v = pd.DataFrame(verdicts)
    crude = chi_square_factor(df, factor)
    has_effect = bool(v["effect"].any()) if not v.empty else False
    no_variation = bool((v["rate_spread"] == 0).all()) if not v.empty else True
    fl, bl = FACTOR_LABELS.get(factor, factor), FACTOR_LABELS.get(by, by)
    if no_variation:
        text = (f"Within each {bl.lower()} group, every {fl.lower()} has exactly the same defect rate. "
                f"{fl} has no effect once {bl.lower()} is taken into account.")
    elif not has_effect:
        text = (f"Within {bl.lower()} groups the {fl.lower()} rates differ only by amounts consistent with chance. "
                f"No evidence of a {fl.lower()} effect after stratification.")
    else:
        hit = ", ".join(str(x) for x in v.loc[v["effect"], by])
        text = f"{fl} still matters within {bl.lower()} group(s): {hit}. Its effect does not disappear."
    return {"factor": factor, "by": by, "table": table, "verdicts": v, "effect_survives": has_effect,
            "crude_p": crude["p_used"], "interpretation": text}


def suspect_within(df: pd.DataFrame, top: dict | None, by: str) -> pd.DataFrame:
    """Suspect vs other jobs within each level of `by` (consistency check)."""
    sus = suspect_mask(df, top)
    rows = []
    for s in levels(df, by):
        sel = df[by] == s
        a, b = df[sel & sus], df[sel & ~sus]
        rows.append({by: s, "suspect_jobs": len(a), "suspect_rate": a["defect"].mean() if len(a) else np.nan,
                     "other_jobs": len(b), "other_rate": b["defect"].mean() if len(b) else np.nan})
    out = pd.DataFrame(rows)
    out["suspect_higher"] = out["suspect_rate"] > out["other_rate"]
    out["comparable"] = (out["suspect_jobs"] > 0) & (out["other_jobs"] > 0)
    return out


def mantel_haenszel(df: pd.DataFrame, top: dict | None, by: str) -> dict:
    """Cochran-Mantel-Haenszel test of suspect vs other, stratified by `by`."""
    from statsmodels.stats.contingency_tables import StratifiedTable
    sus = suspect_mask(df, top)
    tables = []
    for s in levels(df, by):
        sel = df[by] == s
        t = pd.crosstab(sus[sel], df.loc[sel, "defect"]).reindex(index=[True, False], columns=[1, 0], fill_value=0)
        if t.to_numpy().sum() > 1:
            tables.append(t.to_numpy().astype(float))
    try:
        st_ = StratifiedTable(tables)
        res = st_.test_null_odds(correction=False)
        return {"stat": float(res.statistic), "p": float(res.pvalue)}
    except Exception:
        return {"stat": float("nan"), "p": float("nan")}


def symptom_profile(df: pd.DataFrame) -> dict:
    """How often defects co-occur with abnormal symptoms (supports plausibility)."""
    cols = [c for c in SYMPTOMS if c in df.columns]
    d = df[df["defect"] == 1]
    if not cols or d.empty:
        return {"share_defects_with_symptoms": float("nan"), "share_ok_with_symptoms": float("nan")}
    abnormal = df[cols].isin(["Abnormal", "High"]).all(axis=1)
    ok = df[df["defect"] == 0]
    return {"share_defects_with_symptoms": float(abnormal[d.index].mean()),
            "share_ok_with_symptoms": float(abnormal[ok.index].mean()) if len(ok) else float("nan")}


def bradford_hill(df: pd.DataFrame, top: dict | None) -> pd.DataFrame:
    rows = []
    if top is None:
        return pd.DataFrame([{"criterion": "All", "status": "Not testable",
                              "evidence": "No pre-job factor is associated with defects."}])
    who = suspect_name(top)
    # Strength
    rr = top["relative_risk"]
    rr_txt = "∞ (no defects without it)" if math.isinf(rr) else f"{rr:.1f}×"
    if top["significant"] and (math.isinf(rr) or rr >= 3):
        s = "Met"
    elif top["significant"] or rr >= 2:
        s = "Partially"
    else:
        s = "Not met"
    rows.append({"criterion": "Strength", "status": s,
                 "evidence": f"Relative risk {rr_txt}; Fisher q = {_fmt_p(top['q_bh'])}."})
    # Consistency
    parts, ok_all, n_cmp = [], True, 0
    for by in ["Maintenance_Station", "Month"]:
        if by == top["factor"]:
            continue
        w = suspect_within(df, top, by)
        w = w[w["comparable"]]
        n_cmp += len(w)
        ok = int(w["suspect_higher"].sum())
        ok_all &= ok == len(w)
        parts.append(f"higher in {ok} of {len(w)} {FACTOR_LABELS[by].lower()}s")
    s = "Not testable" if n_cmp == 0 else ("Met" if ok_all else "Partially")
    rows.append({"criterion": "Consistency", "status": s, "evidence": f"Defect rate with {who}: " + "; ".join(parts) + "."})
    # Temporality
    rows.append({"criterion": "Temporality", "status": "Partially",
                 "evidence": "Tool status is known before the job and the defect is found after it, "
                             "but the data has no timestamps to prove the order."})
    # Plausibility
    sp = symptom_profile(df)
    tool_related = top["factor"] in ("Tool_ID", "Tool_Status")
    if tool_related and sp["share_defects_with_symptoms"] == 1.0:
        s, ev = "Met", ("A tension tool out of calibration sets belt tension wrongly, which causes heat and vibration. "
                        "100% of defects show high temperature and vibration, matching that mechanism.")
    elif tool_related:
        s, ev = "Partially", (f"Mechanism is plausible; {sp['share_defects_with_symptoms']:.0%} of defects "
                              "show the expected heat and vibration signature.")
    else:
        s, ev = "Partially", "No clear engineering mechanism links this factor to belt damage."
    rows.append({"criterion": "Plausibility", "status": s, "evidence": ev})
    # Specificity
    if top["share_of_defects"] == 1.0 and top["rate_rest"] == 0:
        s, ev = "Met", f"All defects involve {who}, and no defects occur without it."
    elif top["share_of_defects"] >= 0.5:
        s, ev = "Partially", f"{top['share_of_defects']:.0%} of defects involve {who}; other causes also exist."
    else:
        s, ev = "Not met", f"Only {top['share_of_defects']:.0%} of defects involve {who}."
    rows.append({"criterion": "Specificity", "status": s, "evidence": ev})
    rows.append({"criterion": "Dose-response", "status": "Not testable",
                 "evidence": "Needs days overdue for calibration or measured tension error; the data only has a yes/no status."})
    rows.append({"criterion": "Experiment", "status": "Not testable",
                 "evidence": "No intervention yet. Recalibrate the tool and compare against a reference tool to confirm."})
    return pd.DataFrame(rows)


def confounding_note(df: pd.DataFrame, top: dict | None) -> str:
    if top is None:
        return "No suspect factor, so no confounding to report."
    if not top["confounded_with"]:
        return (f"{top['label']} '{top['level']}' does not perfectly overlap with any other pre-job factor, "
                "so its effect can be separated from the others in this data.")
    others = ", ".join(f"{FACTOR_LABELS[c['factor']].lower()} '{c['level']}'" for c in top["confounded_with"])
    return (f"{top['label']} '{top['level']}' and {others} always occur together in this data. "
            "The data therefore cannot tell whether the problem is this specific tool (a faulty unit) or the "
            "missed calibration (a process lapse). Both point to the same action: take it out of service, recalibrate it, "
            "then run a controlled test against a reference tool. If defects stop after recalibration, calibration was the cause.")
