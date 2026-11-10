"""Dashboard page for release v2 files (the real GAL Case 3 data), rendered by app.py when an upload is v2.

Same layout as the sample-data page: alert banner, four KPIs, aircraft status board, then four tabs that each
answer one question with a computed answer line and one main visual. Works with the unlabelled test inputs
(model predictions only) and with the labelled training workbook (predictions next to actual defects).
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src import charts as ch
from src import v2

_n = [0]


def _chart(fig, height: int = 330):
    _n[0] += 1
    fig.update_layout(height=height)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False}, key=f"v2_chart_{_n[0]}")


def _answer(text: str):
    st.markdown(f'<div class="answer">{html.escape(text)}</div>', unsafe_allow_html=True)


@st.cache_resource(show_spinner="Loading the trained model...")
def _bundle():
    return v2.load_bundle()


@st.cache_data(show_spinner="Scoring every screening episode...")
def _score(raw: pd.DataFrame) -> pd.DataFrame:
    return v2.score(raw, _bundle())


def render(raw: pd.DataFrame, source: str) -> None:
    missing = v2.missing_columns(raw)
    if missing:
        st.error(f"This looks like a Case 3 v2 file, but it is missing: **{', '.join(missing)}**.")
        return
    if not v2.MODEL_PATH.exists():
        st.error("No trained model found. Run `python -m case3.train` in Backend/ first (see Backend/README.md).")
        return

    df = _score(raw)
    thr = _bundle()["threshold"]
    report = v2.load_report() or {}
    labelled = v2.has_labels(df)
    n, n_yes = len(df), int(df["pred"].sum())
    board = v2.aircraft_board(df)
    n_air_flag = int((board["Band"] == "High Risk").sum())
    fleet = "B787 " if df["Aircraft_ID"].astype(str).str.upper().str.startswith("B787").all() else ""

    # ------------------------------------------------------------------ alert banner
    headline = (f"{n_air_flag} {fleet}aircraft {'has' if n_air_flag == 1 else 'have'} screening episodes "
                "predicted to have a belt defect." if n_air_flag else
                f"No {fleet}aircraft have episodes predicted to have a belt defect.")
    evidence = (f"{n_yes} of {n} screening episodes ({n_yes / n:.1%}) predicted Yes by the trained model "
                f"(threshold {thr}).")
    m = v2.metrics(df)
    if labelled:
        evidence += (f" Actual: {int(df['actual'].sum())} defects ({df['actual'].mean():.1%}); on this file the "
                     f"model scores F1 {m['f1']:.2f} (precision {m['precision']:.0%}, recall {m['recall']:.0%}).")
    months = sorted(df["Month"].dropna().unique())
    span = f"{months[0]} to {months[-1]}" if months else "no dates"
    st.markdown(
        f'<div class="fleet-alert{"" if n_air_flag else " ok"}"><div class="fa-top">'
        f'<span class="fa-label">● FLEET ALERT</span><span class="fa-tag">{html.escape(source)} · {n} episodes · '
        f'{df["Aircraft_ID"].nunique()} aircraft · {html.escape(span)}</span></div>'
        f'<div class="fa-head">{html.escape(headline)}</div>'
        f'<div class="fa-sub">Possible contributing factor: {html.escape(v2.calibration_finding(df))}</div>'
        f'<div class="fa-evidence">{html.escape(evidence)}</div></div>', unsafe_allow_html=True)

    # ------------------------------------------------------------------ KPIs
    tools = v2.tool_calibration(df)
    k = st.columns(4)
    k[0].metric("Screening episodes", n)
    k[1].metric("Predicted defects", n_yes, help=f"{n_yes / n:.1%} of episodes")
    if labelled:
        k[2].metric("Actual defects", int(df["actual"].sum()), help=f"{df['actual'].mean():.1%} of episodes")
    else:
        k[2].metric("Aircraft flagged", n_air_flag, help=f"of {df['Aircraft_ID'].nunique()} aircraft")
    k[3].metric(f"Rate with {tools.index[0]}" if len(tools) else "Highest tool rate",
                f"{tools['rate'].iloc[0]:.0%}" if len(tools) else "n/a",
                help=f"{int(tools['defects'].iloc[0])} of {int(tools['jobs'].iloc[0])} jobs" if len(tools) else None)

    # ------------------------------------------------------------------ aircraft status board
    hi = {c: df[c].quantile(0.9) for c in ["Belt_Temperature_C", "Belt_Vibration_mm_s", "Abs_Tension_Diff_Pct"]}
    cal_hi = df["Days_Since_Tool_Calibration"].quantile(0.9)

    def chip(label, val, col, fmt):
        if pd.isna(val):
            return f'<span class="chip">{label}: –</span>'
        bad = val >= hi[col]
        return f'<span class="chip{" bad" if bad else ""}">{label}: {fmt.format(val)}</span>'

    key = {"High Risk": "High", "Medium": "Medium", "Normal": "Normal"}
    rows = []
    for _, r in board.iterrows():
        td = r["Tension_Diff_Pct"]
        td_txt = "–" if pd.isna(td) else f"{td:+.1f}%"
        td_cls = ' class="tbad"' if pd.notna(td) and abs(td) >= hi["Abs_Tension_Diff_Pct"] else ""
        days = r["Days_Since_Tool_Calibration"]
        badge = (f'<span class="badge">{days:.0f} days since calibration</span>'
                 if pd.notna(days) and days >= cal_hi else "")
        rows.append(
            f'<tr><td class="ac">{html.escape(str(r["Aircraft_ID"]))}</td>'
            f'<td><span class="dot d-{key[r["Band"]]}"></span><span class="st">{r["Band"]}</span></td>'
            f'<td{td_cls}>{td_txt}</td>'
            f'<td>{chip("Temp", r["Belt_Temperature_C"], "Belt_Temperature_C", "{:.0f} °C")}'
            f'{chip("Vibration", r["Belt_Vibration_mm_s"], "Belt_Vibration_mm_s", "{:.1f} mm/s")}</td>'
            f'<td>{html.escape(str(r["Tool_ID"]))}{badge}</td>'
            f'<td>{r["Defect_Probability"]:.0%}</td></tr>')
    st.html('<div class="board-wrap"><table class="board"><thead><tr><th>Aircraft</th><th>Belt Status</th>'
            '<th>Tension Difference</th><th>Belt Readings</th><th>Tool</th><th>Defect risk</th></tr></thead>'
            "<tbody>" + "".join(rows) + "</tbody></table></div>")
    counts = board["Band"].value_counts()
    st.markdown(f'<div class="board-note">{len(board)} aircraft, each shown by its highest-risk episode: '
                + " · ".join(f"{counts.get(b, 0)} {b}" for b in v2.BANDS)
                + f". High Risk = model predicts a defect (risk ≥ {thr:.0%}); Medium = risk ≥ {thr / 2:.0%}. "
                  "Red readings are in the top 10% of this file.</div>", unsafe_allow_html=True)

    rc, rate_label = v2.rate_col(df)
    tabs = st.tabs(["Why are defects happening?", "When do defects happen?",
                    "Can we predict defects before the job?", "What should maintenance do?"])

    # ------------------------------------------------------------------ 1. Why
    with tabs[0]:
        _answer(v2.calibration_finding(df))
        c1, c2 = st.columns(2)
        with c1:
            r = v2.rate_by(df, "Tool_ID")
            _chart(ch.rate_bar(r, f"{rate_label} by tool", "Tool", tools.index[0] if len(tools) else None,
                               y_label=f"{rate_label} (% of jobs)", auto_range=True))
        with c2:
            b = v2.rate_by(df, "Belt_Batch_ID")
            worst_b = b.sort_values("rate", ascending=False)["level"].iloc[0]
            _chart(ch.rate_bar(b, f"{rate_label} by belt batch", "Batch", worst_b,
                               y_label=f"{rate_label} (% of jobs)", auto_range=True))
        imp = v2.load_importance()
        if imp is not None:
            top3 = ", ".join(v2.LABELS.get(c, c) for c in imp.index[:3])
            st.markdown(f"**Strongest signals in the model:** {top3}. These are associations learned from the "
                        "training data, not proof of cause.")

    # ------------------------------------------------------------------ 2. When
    with tabs[1]:
        mm = v2.monthly(df)
        col = "actual_rate" if labelled else "predicted_rate"
        peak = mm.loc[mm[col].idxmax()]
        word = "defect rate" if labelled else "predicted defect rate"
        trend = ""
        if len(mm) >= 2:
            first, last = mm[col].iloc[0], mm[col].iloc[-1]
            trend = f"; it went from {first:.1%} in {mm['Month'].iloc[0]} to {last:.1%} in {mm['Month'].iloc[-1]}"
        _answer(f"The {word} peaks in {peak['Month']} at {peak[col]:.1%}{trend}.")
        _chart(ch.monthly_rate_chart(mm, f"{'Actual and predicted' if labelled else 'Predicted'} defect rate by "
                                         "month"), height=380)

    # ------------------------------------------------------------------ 3. Predict
    with tabs[2]:
        val = report.get("validation", {})
        if val:
            parts = [f"{lbl} {val[k]['f1']:.2f}" for k, lbl in [("cv_oof", "cross-validation"),
                                                                  ("unseen_summer_2024", "unseen summer 2024"),
                                                                  ("unseen_2025", "unseen 2025")] if k in val]
            _answer("Yes. Validated F1 on rows the model never saw: " + ", ".join(parts) + ".")
        if labelled:
            st.markdown(f"**On this file:** F1 {m['f1']:.2f} · {m['tp']} defects caught, {m['fn']} missed, "
                        f"{m['fp']} false alarms (precision {m['precision']:.0%}, recall {m['recall']:.0%}).")
            st.caption("If this file is the training data, the model has already seen these rows, so this score "
                       "is optimistic; the validated scores above are the honest estimate.")
        st.markdown(f"**How it works:** CatBoost + LightGBM trained on 10,000 labelled episodes; an episode is "
                    f"predicted Yes when its defect risk is at least {thr:.0%}. Inputs are the screening "
                    "measurements, maintenance context and 30-day duty summaries in each row.")
        imp = v2.load_importance()
        if imp is not None:
            _chart(ch.importance_bar(imp, "What the model looks at", v2.LABELS), height=360)

    # ------------------------------------------------------------------ 4. Act
    with tabs[3]:
        insp = v2.inspection_list(df)
        _answer(f"Inspect {len(insp)} screening episodes on {insp['Aircraft'].nunique() if len(insp) else 0} "
                f"aircraft first: the model predicts a defect for each of them.")
        data, problems = v2.submission(df)
        d1, d2, d3 = st.columns([2, 1, 1])
        if problems:
            d1.error("Submission check failed: " + "; ".join(problems))
        else:
            d1.success(f"case_3_predictions.csv passes every format check ({n} rows, Yes/No).")
        d2.download_button("Inspection list", insp.to_csv(index=False).encode(), "inspection_list.csv",
                           "text/csv", icon=":material/download:", width="stretch")
        d3.download_button("Submission CSV", data, "case_3_predictions.csv", "text/csv",
                           icon=":material/download:", width="stretch", type="primary")
        st.dataframe(insp, width="stretch", hide_index=True, height=min(35 * (len(insp) + 1) + 3, 360))
