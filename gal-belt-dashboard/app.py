"""B787 Engine Belt Defect Investigation: Streamlit UI only. All analysis lives in src/."""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from src import charts as ch
from src import impact, model, rca, stats
from src import data as data_mod
from src.data import FACTOR_LABELS, NORMAL_STATUS, SYMPTOMS, load, month_order, summary

st.set_page_config(page_title="B787 Belt Defect Investigation", page_icon="✈️", layout="wide")

st.markdown("""
<style>
  html, body, [class*="css"] { font-size: 16px; }
  /* Translucent tints + inherited text colour, so every box reads in both light and dark theme. */
  .alert { background:rgba(208,59,59,0.14); border-left:6px solid #d03b3b; padding:14px 18px; border-radius:6px;
           color:inherit; font-size:1.08rem; margin:6px 0 12px 0; }
  .card { border:1px solid rgba(128,128,128,0.35); border-radius:8px; padding:14px 18px;
          background:rgba(128,128,128,0.06); color:inherit; }
  .band-High { background:rgba(208,59,59,0.14); border-left:8px solid #d03b3b; }
  .band-Medium { background:rgba(224,161,0,0.16); border-left:8px solid #E0A100; }
  .band-Low { background:rgba(12,163,12,0.14); border-left:8px solid #0ca30c; }
  .band-title { font-size:1.7rem; font-weight:700; margin:0; }
  .muted { opacity:0.75; }
  .proves { color:inherit; opacity:0.8; font-size:0.95rem; border-left:3px solid #9aa3ad; padding-left:10px; margin:4px 0 14px 0; }
  .present h1 { font-size:2.4rem; }
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------- cached data + analysis

@st.cache_data(show_spinner=False)
def load_cached(content: bytes | None, name: str | None, default_path: str):
    return load(content, name) if content is not None else load(default_path, default_path)


@st.cache_data(show_spinner="Running analysis...")
def analyse(df: pd.DataFrame) -> dict:
    top = stats.detect_top_factor(df)
    out = {"top": top, "summary": summary(df), "alert": stats.alert_text(df, top),
           "ranking": stats.factor_ranking(df), "assoc": stats.association_table(df),
           "monthly": stats.monthly_summary(df, top), "pchart": stats.p_chart(df), "trend": stats.cochran_armitage(df),
           "bh": stats.bradford_hill(df, top), "confounding": stats.confounding_note(df, top),
           "gate": impact.calibration_gate(df), "affected": impact.affected_aircraft(df, top),
           "actions": impact.recommended_actions(top), "fishbone": rca.fishbone(df, top),
           "whys": rca.five_whys(df, top), "chain": rca.causal_chain_dot(top),
           "overall_bayes": stats.bayes_overall(df)}
    out["bayes"] = pd.concat([stats.bayes_rates(df, f).assign(factor_label=FACTOR_LABELS[f])
                              for f in stats.factors_present(df, include_symptoms=False)], ignore_index=True)
    out["strata"] = {by: stats.stratify(df, "Maintenance_Station", by)
                     for by in ["Tool_ID", "Tool_Status"] if by in df.columns}
    out["cmh"] = stats.mantel_haenszel(df, top, "Maintenance_Station") if top else None
    has_two_classes = df["defect"].nunique() == 2
    out["tree"] = model.fit_tree(df) if model.features_for(df) else None
    out["logit"] = model.fit_logistic(df) if has_two_classes and model.features_for(df) else None
    out["firth"] = model.fit_firth(df) if has_two_classes and model.features_for(df) else None
    out["validation"] = model.validate_pre_job(df)
    out["leakage"] = model.leakage_demo(df) if has_two_classes else None
    return out


# ----------------------------------------------------------------------------- sidebar

with st.sidebar:
    st.header("Data")
    upload = st.file_uploader("Upload maintenance records (CSV or XLSX)", type=["csv", "xlsx"],
                              help="Same columns as the GAL sample. Leave empty to use the bundled 30-record file.")
    present = st.toggle("Presentation mode", value=False, help="Hides data tables and enlarges charts for the demo.")
    st.header("Risk thresholds")
    high_t = st.slider("High risk from", 0, 100, 50, 5, format="%d%%") / 100
    med_t = st.slider("Medium risk from", 0, 100, 20, 5, format="%d%%") / 100
    if med_t > high_t:
        st.warning("Medium threshold is above High; using High for both.")
        med_t = high_t
    with st.expander("Cost assumptions (replace with GAL figures)"):
        cost = impact.CostAssumptions(
            cost_per_aog_hour=st.number_input("Cost per AOG hour (USD)", 0.0, 1e6, 10_000.0, 1_000.0),
            aog_hours_per_failure=st.number_input("AOG hours per in-service belt failure", 0.0, 500.0, 24.0, 1.0),
            share_to_in_service=st.slider("Share of defects that would fail in service", 0, 100, 30, 5,
                                          format="%d%%") / 100,
            cost_per_reinspection=st.number_input("Cost per aircraft re-inspection (USD)", 0.0, 1e6, 1_500.0, 100.0),
        )
    st.caption("Prototype for the MoIAT x GAL hackathon. Not for operational aircraft use.")

res = load_cached(upload.getvalue() if upload else None, upload.name if upload else None, str(data_mod.DEFAULT_DATA))

st.title("B787 Engine Belt Defect Investigation")
if not res.ok:
    if res.missing:
        st.error("The file is missing required columns: **" + ", ".join(res.missing) + "**. "
                 "Expected at least: Month, Maintenance_Station, Tool_ID, Tool_Status, Belt_Defect.")
    else:
        st.error("Could not read any usable rows. " + "; ".join(x["detail"] for x in res.log))
    st.stop()

df = res.df
A = analyse(df)
top, S = A["top"], A["summary"]
BIG = present
sus = stats.suspect_mask(df, top)
suspect_label = stats.suspect_name(top)


_chart_no = [0]


def chart(fig):
    _chart_no[0] += 1  # unique key: two charts with identical content must not collide
    st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False}, key=f"chart_{_chart_no[0]}")


def table(data, **kw):
    if not present:
        st.dataframe(data, width="stretch", hide_index=True, **kw)


def proves(text: str):
    st.markdown(f'<div class="proves"><b>What this shows / does not show:</b> {text}</div>', unsafe_allow_html=True)


def pct(v):
    return "n/a" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.0%}"


# ----------------------------------------------------------------------------- header

st.caption(f"Source: {res.source} · {S['records']} records · {S['aircraft']} aircraft · "
           f"{S['defects']} defects · months: {', '.join(S['months'])}")
st.markdown(f'<div class="alert">⚠️ <b>ALERT:</b> {A["alert"]}</div>', unsafe_allow_html=True)

others = df[~sus]
k = st.columns(5)
k[0].metric("Overall defect rate", pct(df["defect"].mean()), help=f"{S['defects']} of {S['records']} jobs")
k[1].metric(f"Defect rate with {top['level'] if top else 'suspect'}",
            pct(df.loc[sus, "defect"].mean()) if sus.any() else "n/a",
            help=f"{int(df.loc[sus, 'defect'].sum())} of {int(sus.sum())} jobs")
k[2].metric("Defect rate, all other jobs", pct(others["defect"].mean()) if len(others) else "n/a",
            help=f"{int(others['defect'].sum())} of {len(others)} jobs")
k[3].metric("Tools needing calibration", df.loc[df["Tool_Status"] != NORMAL_STATUS, "Tool_ID"].nunique())
k[4].metric("Aircraft requiring follow-up", A["affected"]["Aircraft_ID"].nunique())

TAB_NAMES = ["Overview", "Why", "When", "Causation", "Prediction", "Root cause", "Action plan", "Data & methods"]
tabs = st.tabs(TAB_NAMES)


# ----------------------------------------------------------------------------- 1. Overview

def style_records(d: pd.DataFrame):
    def row_style(r):
        # Translucent tints (no fixed text colour) stay readable in light and dark theme.
        base = "background-color:rgba(208,59,59,0.18)" if r.get("Belt_Defect") == "Yes" else ""
        return [base] * len(r)

    def cell(v):
        if v == "Needs Calibration":
            return "background-color:rgba(224,161,0,0.35); font-weight:600"
        if v in ("Abnormal", "High"):
            return "color:#d64545; font-weight:600"
        return ""

    return d.style.apply(row_style, axis=1).map(cell)


with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        rates = stats.rates_by_factor(df, "Tool_ID")
        if top and top["factor"] == "Tool_ID" and top["rate_rest"] == 0:
            title = f"All defects occurred with {top['level']}"
        elif top:
            title = f"{top['level']} has the highest defect rate"
        else:
            title = "Defect rate by tool"
        hl = top["level"] if top and top["factor"] == "Tool_ID" else None
        chart(ch.rate_bar(rates, title, "Tool", hl, BIG))
    with c2:
        p = stats.pareto(df, "Tool_ID")
        if S["defects"]:
            lead = p.iloc[0]
            ptitle = f"{lead['level']} accounts for {lead['defects'] / S['defects']:.0%} of all defects"
        else:
            ptitle = "No defects recorded"
        chart(ch.pareto_chart(p, ptitle, BIG))

    if not present:
        st.subheader("All records")
        f1, f2, f3, f4 = st.columns(4)
        sel_tool = f1.multiselect("Tool", sorted(df["Tool_ID"].unique()))
        sel_station = f2.multiselect("Station", sorted(df["Maintenance_Station"].unique()))
        sel_month = f3.multiselect("Month", month_order(df["Month"].unique()))
        sel_def = f4.multiselect("Defect", ["Yes", "No"])
        view = df.drop(columns="defect")
        for col, sel in [("Tool_ID", sel_tool), ("Maintenance_Station", sel_station), ("Month", sel_month),
                         ("Belt_Defect", sel_def)]:
            if sel:
                view = view[view[col].isin(sel)]
        st.caption(f"{len(view)} of {len(df)} records. Red rows = defect · amber = tool needs calibration · "
                   "red text = abnormal/high reading.")
        st.dataframe(style_records(view), width="stretch", hide_index=True)


# ----------------------------------------------------------------------------- 2. Why

with tabs[1]:
    st.subheader("Which factors are linked to defects?")
    rk = A["ranking"]
    if rk.empty:
        st.info("Not enough variation in the data to rank factors.")
    else:
        rk = rk[rk["rate"] >= rk["rate_rest"]] if (rk["rate"] > rk["rate_rest"]).any() else rk
        show = pd.DataFrame({
            "Factor": rk["factor"].map(FACTOR_LABELS), "Level": rk["level"], "Role": rk["role"],
            "Defects / jobs": [f"{d} / {n}" for d, n in zip(rk["defects"], rk["jobs"])],
            "Defect rate": rk["rate"], "Rate elsewhere": rk["rate_rest"],
            "Relative risk": [("∞" if math.isinf(v) else "–" if math.isnan(v) else f"{v:.1f}×")
                              for v in rk["relative_risk"]],
            "Fisher p": rk["p_fisher"].map(stats.fmt_p), "BH q": rk["q_bh"].map(stats.fmt_p),
            "Cramér's V": rk["cramers_v"].round(2)})
        if present:
            st.markdown(f"**Top pre-job factor:** {suspect_label}. " + A["alert"].split(". ", 1)[-1])
        else:
            st.dataframe(show, width="stretch", hide_index=True, column_config={
                "Defect rate": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
                "Rate elsewhere": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1)})
        proves("Fisher's exact test checks each group against all other jobs; the BH q-value corrects for running "
               f"{len(A['ranking'])} tests at once. A small q means the link is unlikely to be chance. It does not prove "
               "cause: symptom rows (condition, temperature, vibration) are perfectly linked too, because they are "
               "part of the defect itself.")

    st.markdown("**Factor-level tests (chi-square / exact)**")
    assoc = A["assoc"]
    if not present:
        st.dataframe(pd.DataFrame({
            "Factor": assoc["factor"].map(FACTOR_LABELS), "Role": assoc["role"], "Groups": assoc["levels"],
            "Chi-square p": assoc["p_chi2"].map(stats.fmt_p),
            "Exact p (small counts)": assoc["p_exact"].map(stats.fmt_p),
            "Cramér's V (0 = none, 1 = perfect)": assoc["cramers_v"].round(2)}), width="stretch", hide_index=True)
    small = [FACTOR_LABELS[r.factor] for r in assoc.itertuples() if r.exact_method]
    if small:
        st.caption(f"Small expected counts (< 5) for: {', '.join(small)}. For these the exact p-value is used "
                   "(Fisher's exact test for two groups, a Fisher-Freeman-Halton permutation test for more).")
    for r in assoc.itertuples():
        if r.note and not r.exact_method:
            st.caption(f"{FACTOR_LABELS[r.factor]}: {r.note}")

    b = A["bayes"]
    stand_out = b[b["ci_low"] > A["overall_bayes"]["post_mean"]]
    btitle = (f"Only {' / '.join(stand_out['level'].astype(str))} sit clearly above the fleet average"
              if len(stand_out) else "No group sits clearly above the fleet average")
    chart(ch.bayes_chart(b, A["overall_bayes"], btitle, BIG))
    proves("Each dot is the estimated defect rate for that group (Bayesian, flat prior); the line is the 90% credible "
           "interval. Wide lines mean few jobs. A group whose whole line is right of the fleet average is a real "
           "outlier in this sample; it does not mean every future job in that group will fail.")
    if not present:
        bt = b.assign(**{"P(rate above rest)": b["p_higher_than_rest"].map(lambda v: f"{v:.0%}")})
        st.dataframe(bt[["factor_label", "level", "jobs", "defects", "post_mean", "ci_low", "ci_high",
                         "P(rate above rest)"]].rename(columns={
            "factor_label": "Factor", "level": "Level", "jobs": "Jobs", "defects": "Defects",
            "post_mean": "Estimated rate", "ci_low": "90% low", "ci_high": "90% high"}).round(3),
            width="stretch", hide_index=True)

    st.markdown("**Tool × station**")
    h1, h2 = st.columns(2)
    defects_ts = df.pivot_table(index="Tool_ID", columns="Maintenance_Station", values="defect", aggfunc="sum",
                                fill_value=0)
    jobs_ts = df.pivot_table(index="Tool_ID", columns="Maintenance_Station", values="defect", aggfunc="count",
                             fill_value=0)
    rows_with_def = defects_ts.index[defects_ts.sum(axis=1) > 0].tolist()
    htitle = (f"Defects appear only in the {', '.join(rows_with_def)} row, at every station"
              if len(rows_with_def) == 1 and (defects_ts.loc[rows_with_def[0]] > 0).all()
              else "Defects by tool and station")
    with h1:
        chart(ch.heatmap(defects_ts, htitle, "Station", "Tool", ch.SEQ_RED, big=BIG,
                         text=defects_ts.map(lambda v: f"{v} defects")))
    with h2:
        chart(ch.heatmap(jobs_ts, "Every tool was used at several stations", "Station", "Tool", ch.SEQ_NAVY, big=BIG,
                         text=jobs_ts.map(lambda v: f"{v} jobs")))


# ----------------------------------------------------------------------------- 3. When

with tabs[2]:
    m = A["monthly"]
    tr = A["trend"]
    rising = len(m) > 1 and m["defects"].iloc[-1] > m["defects"].iloc[0]
    if top and (m["defects"] == m["suspect_defects"]).all() and rising:
        mtitle = f"Defects rose only as {top['level']} was used more"
    elif top and (m["defects"] == m["suspect_defects"]).all():
        mtitle = f"Defects move exactly with use of {top['level']}"
    else:
        mtitle = "Monthly jobs and defects"
    chart(ch.monthly_chart(m, top["level"] if top else "suspect", mtitle, BIG))
    if not present:
        st.dataframe(m.rename(columns={"month": "Month", "jobs": "Jobs", "defects": "Defects", "rate": "Defect rate",
                                       "suspect_jobs": f"Jobs with {top['level'] if top else 'suspect'}",
                                       "suspect_defects": "Defects in those jobs"}),
                     width="stretch", hide_index=True,
                     column_config={"Defect rate": st.column_config.NumberColumn(format="percent")})

    pc = A["pchart"]
    ptitle = ("Monthly defect rate stays inside control limits" if not pc["out_months"]
              else f"{', '.join(pc['out_months'])} outside control limits")
    chart(ch.p_chart_fig(pc, ptitle, BIG))
    st.markdown(f"**p-chart:** {pc['interpretation']}")
    st.markdown(f"**Cochran-Armitage trend test:** z = {tr['z']:.2f}, two-sided p = {stats.fmt_p(tr['p'])}. "
                f"{tr['interpretation']}")
    proves("With about 10 jobs a month, the limits are wide: the chart can only flag big jumps. "
           "No significant trend means the 'increase' in defects is explained by how often the suspect tool was used, "
           "not by a fleet-wide deterioration over time.")
    st.info("**Survival analysis (Kaplan-Meier / Weibull)** would answer *how long until a belt fails*. It needs "
            "install dates, flight hours or cycles per belt, which this data does not have. "
            "With those fields the same dashboard could show time-to-failure curves per tool.")


# ----------------------------------------------------------------------------- 4. Causation

STATUS_ICON = {"Met": "✅ Met", "Partially": "🟡 Partially", "Not met": "❌ Not met", "Not testable": "⚪ Not testable"}

with tabs[3]:
    st.subheader("Is it the station, or the tool? Stratified comparison")
    st.caption("Mantel-Haenszel logic: compare stations within each tool group. If the station differences vanish, "
               "the station was only a stand-in for which tool was used there.")
    for by, res_s in A["strata"].items():
        by_label = FACTOR_LABELS[by]
        title = ("Within each " + by_label.lower() + ", stations have the same defect rate"
                 if not res_s["effect_survives"] else f"Station still matters within some {by_label.lower()} groups")
        chart(ch.small_multiples(res_s["table"], "Maintenance_Station", by, title, "Station", by_label, BIG))
        st.markdown(f"**{res_s['interpretation']}** (crude station p = {stats.fmt_p(res_s['crude_p'])})")
        if not present:
            v = res_s["verdicts"].rename(columns={"jobs": "Jobs", "rate_spread": "Max − min station rate",
                                                  "p": "Within-group p", "effect": "Station effect?"})
            st.dataframe(v, width="stretch", hide_index=True)
    if A["cmh"] and not math.isnan(A["cmh"]["p"]):
        st.markdown(f"**Cochran-Mantel-Haenszel test** (suspect vs other jobs, stratified by station): "
                    f"χ² = {A['cmh']['stat']:.1f}, p = {stats.fmt_p(A['cmh']['p'])}. "
                    "The suspect effect holds after accounting for station.")
    proves("Stratification removes station as an explanation. It cannot remove factors that were never recorded "
           "(technician, belt batch), so it narrows the cause but does not prove it.")

    st.subheader("Bradford Hill checklist")
    bh = A["bh"].assign(status=lambda d: d["status"].map(lambda s: STATUS_ICON.get(s, s)))
    st.table(bh.rename(columns={"criterion": "Criterion", "status": "Status", "evidence": "Evidence"})
             .set_index("Criterion"))

    st.subheader("Proposed causal chain")
    st.graphviz_chart(A["chain"], width="stretch")
    st.caption("Solid boxes are in the data. The dashed box (belt tension) is inferred: tension was not measured.")
    st.warning("**Confounding:** " + A["confounding"])


# ----------------------------------------------------------------------------- 5. Prediction

with tabs[4]:
    if A["logit"] is None:
        st.info("The prediction model needs both defect and non-defect jobs, and at least one pre-job factor that varies.")
    else:
        st.subheader("Pre-job risk check")
        st.caption("Pick the job set-up before work starts. Uses only information available at that point.")
        lr = A["logit"]
        feats = lr["features"]
        cols = st.columns(len(feats))
        defaults = {}
        if top:
            defaults[top["factor"]] = top["level"]
            for c in top["confounded_with"]:
                defaults[c["factor"]] = c["level"]
        job = {}
        for col, f in zip(cols, feats):
            opts = stats.levels(df, f)
            idx = opts.index(defaults[f]) if defaults.get(f) in opts else 0
            job[f] = col.selectbox(FACTOR_LABELS[f], opts, index=idx, key=f"job_{f}")
        res_c = model.check_job(df, lr, job, high_t, med_t)
        icon = {"High": "⛔", "Medium": "⚠️", "Low": "✅"}[res_c["band"]]
        bayes_txt = ""
        if res_c["bayes"]:
            bb = res_c["bayes"]
            bayes_txt = (f"<br>Past jobs with tool status <b>{job.get('Tool_Status')}</b>: {int(bb['defects'])} of "
                         f"{int(bb['jobs'])} defective. Estimated rate {bb['post_mean']:.0%} "
                         f"(90% interval {bb['ci_low']:.0%}–{bb['ci_high']:.0%}).")
        st.markdown(
            f'<div class="card band-{res_c["band"]}"><p class="band-title">{icon} {res_c["band"]} risk · '
            f'{res_c["probability"]:.0%}</p><b>Main reason:</b> {res_c["reason"]}{bayes_txt}'
            f'<br><b>Recommendation:</b> {res_c["recommendation"]}</div>', unsafe_allow_html=True)
        if top and top["confounded_with"]:
            tool_lvl = job.get("Tool_ID")
            seen = df[(df["Tool_ID"] == tool_lvl) & (df["Tool_Status"] == job.get("Tool_Status"))] \
                if "Tool_ID" in job and "Tool_Status" in job else df
            if len(seen) == 0:
                st.caption("ℹ️ This tool/status combination never occurred in the data, so the model is guessing "
                           "between the two confounded explanations. Treat this score as a what-if, not evidence.")
        proves("The score is a probability from a penalised logistic regression trained on past jobs. It ranks risk; "
               "it is not a certified failure prediction and must not replace the approved maintenance procedure.")

        with st.expander("Why these features?", expanded=not present):
            st.dataframe(pd.DataFrame([{"Column": c, "Used?": "✅ Yes" if c in feats else "❌ No",
                                        "Reason": model.FEATURE_REASONS[c]}
                                       for c in list(model.FEATURE_REASONS) if c in df.columns]),
                         width="stretch", hide_index=True)

        st.subheader("What the model learned")
        t1, t2 = st.columns([1, 1])
        with t1:
            st.markdown("**Decision tree (max depth 2) as a rule:**")
            for rule in A["tree"]["english"]:
                st.markdown(f"- {rule}")
            st.graphviz_chart(A["tree"]["dot"], width="stretch")
        with t2:
            st.markdown("**Logistic regression (L2-penalised, balanced classes):**")
            coef = lr["coefficients"].head(8)
            table(coef.assign(coefficient=coef["coefficient"].round(2),
                              odds_multiplier=coef["odds_multiplier"].round(2)).rename(columns={
                "factor": "Factor", "level": "Level", "coefficient": "Coefficient",
                "odds_multiplier": "Odds multiplier"}))
            st.caption("Why penalised? The outcome is perfectly separated by tool status, so an ordinary logistic "
                       "regression pushes coefficients to infinity and never converges. The L2 penalty keeps them finite. "
                       "Because tool and status always occur together, the model splits the weight evenly between them.")
            fi = A["firth"]
            if fi is not None:
                ft = fi["coefficients"]
                ft = ft[ft["term"] != "(intercept)"]
                ft = ft.loc[ft["coefficient"].abs().sort_values(ascending=False).index].head(3)
                ft = ft.assign(term=ft["term"].map(lambda t: next(
                    (f"{FACTOR_LABELS[f]} = {t[len(f) + 1:]}" for f in FACTOR_LABELS if t.startswith(f + "_")), t)))
                st.markdown("**Cross-check, Firth penalised logistic regression:** " +
                            ("converged. " if fi["converged"] else "did not fully converge. ") +
                            "Largest effects (vs reference level): " + "; ".join(
                                f"{t} ×{o:.0f} odds" if o >= 10 else f"{t} ×{o:.2f} odds"
                                for t, o in zip(ft["term"], ft["odds_multiplier"])) + ".")
        chart(ch.risk_probs_chart(lr["fitted"], high_t, med_t, BIG))

        st.subheader("How well does it validate?")
        val = A["validation"]
        mcols = st.columns(2)
        for col, name, key in [(mcols[0], "Logistic regression", "logistic"), (mcols[1], "Decision tree", "tree")]:
            v = val[key]
            with col:
                st.markdown(f"**{name}: leave-one-out cross-validation**")
                if v["loo"] is None:
                    st.info(" ".join(v["warnings"]))
                    continue
                mm = st.columns(3)
                mm[0].metric("ROC-AUC", f"{v['loo']['auc']:.2f}")
                mm[1].metric("Recall", f"{v['loo']['recall']:.0%}", help="Share of real defects flagged")
                mm[2].metric("Precision", f"{v['loo']['precision']:.0%}", help="Share of flags that were real defects")
                if v["kfold"]:
                    st.caption(f"Stratified {v['kfold']['k']}-fold: AUC {v['kfold']['auc']:.2f}, "
                               f"recall {v['kfold']['recall']:.0%}, precision {v['kfold']['precision']:.0%}.")
                chart(ch.confusion_fig(v["loo"]["confusion"], f"{v['loo']['tp']} of "
                                       f"{v['loo']['tp'] + v['loo']['fn']} defects caught on unseen jobs", BIG))
        for w in val["logistic"]["warnings"]:
            st.warning(w)
        proves("Each job was predicted by a model that never saw it. A perfect score here means the tool/status "
               "pattern is clean in these 30 jobs. It does not prove the model will be perfect on new jobs, and it "
               "cannot tell the tool apart from its calibration status.")

        lk = A["leakage"]
        if lk and lk["validation"]["loo"]:
            st.subheader("Leakage demo: a model that looks perfect but is useless")
            lv = lk["validation"]["loo"]
            st.error(f"A model trained on **{', '.join(FACTOR_LABELS[f] for f in lk['features'])}** scores "
                     f"AUC {lv['auc']:.2f}, recall {lv['recall']:.0%}. {lk['explanation']}")


# ----------------------------------------------------------------------------- 6. Root cause

FISH_ICON = {"Confirmed": "🔴", "Confirmed but confounded": "🟠", "Ruled out by stratification": "🟢",
             "Not in data": "⚪", "Not testable": "⚪", "Possible": "🟡", "Not supported": "🟢", "Not confirmed": "🟢"}

with tabs[5]:
    st.subheader("Fishbone (6M): where could the cause sit?")
    fb = A["fishbone"]
    fcols = st.columns(3)
    for i, r in enumerate(fb.itertuples()):
        with fcols[i % 3]:
            st.markdown(f'<div class="card" style="margin-bottom:12px"><b>{r.category}</b><br>'
                        f'{FISH_ICON.get(r.status, "")} <b>{r.status}</b><br><span class="muted">'
                        f'{r.evidence}</span></div>', unsafe_allow_html=True)
    st.subheader("5 Whys")
    for i, w in enumerate(A["whys"], 1):
        st.markdown(f"**{i}. {w['why']}**  \n→ {w['because']}")
    if top:
        st.error("**Conclusion: maintenance process gap.** The evidence points to a tool that was used while it needed "
                 "calibration, and to the absence of a check that would have stopped it, not to a station, a month or "
                 "a fleet-wide wear problem.")


# ----------------------------------------------------------------------------- 7. Action plan

with tabs[6]:
    st.subheader("Aircraft that require inspection")
    aff = A["affected"]
    if aff.empty:
        st.success("No aircraft need follow-up based on this data.")
    else:
        st.markdown(f"**{aff['Aircraft_ID'].nunique()} aircraft** need follow-up "
                    f"({(aff['Priority'].str.startswith('1')).sum()} high priority).")
        st.dataframe(aff, width="stretch", hide_index=True)
        st.download_button("Download inspection list (CSV)", aff.to_csv(index=False).encode(),
                           "aircraft_inspection_list.csv", "text/csv", icon=":material/download:")

    st.subheader("Recommended actions")
    st.dataframe(pd.DataFrame(A["actions"]).rename(columns={"action": "Action", "why": "Why", "owner": "Owner"}),
                 width="stretch", hide_index=True)

    st.subheader("Impact of a calibration gate")
    g = A["gate"]
    gc1, gc2 = st.columns([3, 2])
    with gc1:
        chart(ch.gate_chart(g, BIG))
    with gc2:
        st.metric("Defects avoided", g["defects_avoided"], help="Defects on jobs where the tool was not in Normal status")
        st.metric("Reduction", f"{g['reduction_pct']:.0f}%")
        st.metric("Jobs that would have needed a different tool", f"{g['jobs_blocked']} of {g['jobs_total']}")
    proves("This is a counterfactual on past data: it assumes the same jobs done with a calibrated tool would not have "
           "produced a defect. That is the hypothesis the recalibration test must confirm.")

    st.subheader("Cost estimate (assumptions, replace with GAL figures)")
    ce = impact.cost_estimate(g["defects_avoided"], aff["Aircraft_ID"].nunique() if not aff.empty else 0, cost)
    cc = st.columns(4)
    cc[0].metric("In-service failures avoided", f"{ce['in_service_failures_avoided']:.1f}")
    cc[1].metric("AOG hours avoided", f"{ce['aog_hours_avoided']:.0f} h")
    cc[2].metric("AOG cost avoided", f"${ce['aog_cost_avoided']:,.0f}")
    cc[3].metric("Re-inspection cost", f"${ce['reinspection_cost']:,.0f}")
    st.markdown(f"**Estimated net benefit over this {len(S['months'])}-month sample: ${ce['net_benefit']:,.0f}** "
                f"= {g['defects_avoided']} defects avoided × {cost.share_to_in_service:.0%} that would fail in service "
                f"× {cost.aog_hours_per_failure:.0f} AOG hours × ${cost.cost_per_aog_hour:,.0f}/h "
                f"− {aff['Aircraft_ID'].nunique() if not aff.empty else 0} re-inspections × "
                f"${cost.cost_per_reinspection:,.0f}.")
    st.caption("All cost inputs are placeholders set in the sidebar. They are not GAL data.")


# ----------------------------------------------------------------------------- 8. Data & methods

with tabs[7]:
    st.subheader("Data-quality log")
    st.dataframe(pd.DataFrame(res.log).rename(columns={"step": "Step", "detail": "Detail"}), width="stretch",
                 hide_index=True)
    st.subheader("Methods")
    st.markdown("""
| Question | Method | Why |
|---|---|---|
| Which groups have more defects? | Defect rate per group; **Fisher's exact test** per group vs rest; **Benjamini-Hochberg** correction | Exact for small counts; BH controls false discoveries across many tests |
| How strong is a factor overall? | **Chi-square** + **Cramér's V**; exact permutation test when expected counts < 5 | Effect size on a 0–1 scale |
| How sure are we of each rate? | **Bayesian Beta(1,1)** posterior, 90% credible interval, P(rate > rest) by Monte Carlo | Honest uncertainty with only 6–19 jobs per group |
| Is it getting worse over time? | **p-chart** (±3σ limits per month), **Cochran-Armitage** trend test | Standard SPC; trend test for ordered months |
| Is the station a cause or a stand-in? | **Stratification** (station within tool / status), **Cochran-Mantel-Haenszel** | Removes confounding by a measured factor |
| Is it causal? | **Bradford Hill** checklist | Structured judgement; flags what cannot be tested |
| Can we warn before the job? | **Decision tree** (depth 2), **L2 logistic regression**, **Firth** cross-check; **leave-one-out** validation | Interpretable; penalties handle perfect separation |
""")
    st.subheader("Limitations")
    st.markdown(f"""
- **Small sample:** {S['records']} jobs, {S['defects']} defects, {len(S['months'])} months. Any result can change with more data.
- **Categorical only:** no measured tension, temperature or vibration values, so no dose-response.
- **Confounding:** in this data the suspect tool and 'needs calibration' always occur together; the data cannot separate them.
- **No causal proof without an intervention:** recalibrate the tool and compare against a reference tool.
- **One record per aircraft:** no history, so no time-to-failure or repeat-defect analysis.
- **Prototype only:** not for operational aircraft use.
""")
    st.subheader("Data that would unlock more")
    st.markdown("""
- **Dates and flight hours/cycles** → survival analysis (time to belt failure), seasonality.
- **Measured belt tension** before and after the job → direct test of the tension mechanism, dose-response.
- **Tool calibration dates** → days overdue as a risk score.
- **Technician ID, engine ID, belt part/batch number** → test the 'Man' and 'Material' branches of the fishbone.
""")
