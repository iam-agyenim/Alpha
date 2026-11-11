"""B787 fleet belt health dashboard (GAL Case 3).

Run from the project root:
    .venv/bin/streamlit run dashboard/app.py
Needs model outputs first: .venv/bin/python scripts/train_and_predict.py
"""
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make belt_defect importable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from belt_defect import config
from belt_defect import fleet_analysis as fa
import agents_tab  # noqa: E402  (dashboard/agents_tab.py)

st.set_page_config(page_title="B787 Belt Health", page_icon="✈️", layout="wide")

# --- Colors: GAL slide look for page chrome, validated chart palette for data ---
NAVY, BLUE, GOLD, PAGE_BG = "#1B2A5A", "#22509C", "#A8873A", "#F3F4F7"
INK, INK_2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
SERIES_ACTUAL, SERIES_PREDICTED = "#2a78d6", "#eb6834"          # categorical slots 1 and 2
STATUS_COLOR = {fa.STATUS_HIGH: "#d03b3b", fa.STATUS_MEDIUM: "#ec835a", fa.STATUS_NORMAL: "#0ca30c"}
TEST_PERIOD_FILL = "rgba(235,104,52,0.07)"                      # faint band behind predicted months
PLOT_CONFIG = {"displayModeBar": False}


# ============================================================================ helpers
def html(markup: str):
    st.markdown(markup, unsafe_allow_html=True)


def pct(value, digits=1, signed=False) -> str:
    """Format a fraction or percent number for display."""
    if pd.isna(value):
        return "—"
    return f"{value:+.{digits}f}%" if signed else f"{value:.{digits}f}%"


def style_figure(fig: go.Figure, height=300, y_suffix="", legend=True) -> go.Figure:
    """Recessive grid/axes, thin marks, hover on, one y-axis."""
    fig.update_layout(
        height=height, margin=dict(l=4, r=8, t=8, b=4), paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family="Inter, system-ui, sans-serif", color=INK_2, size=12), showlegend=legend,
        legend=dict(orientation="h", y=1.08, x=0, font=dict(color=INK_2)), hovermode="x unified",
        barcornerradius=4, bargap=0.35,
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=AXIS, font_color=INK),
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickfont=dict(color=MUTED), title=None)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED), title=None, ticksuffix=y_suffix)
    return fig


def shade_test_period(fig: go.Figure, data: fa.FleetData):
    """Light band + label over the months that are model predictions."""
    start = data.test.month.min() - pd.Timedelta(days=15)
    end = data.test.month.max() + pd.Timedelta(days=15)
    fig.add_vrect(x0=start, x1=end, fillcolor=TEST_PERIOD_FILL, line_width=0, layer="below",
                  annotation_text="Test period (predicted)", annotation_position="top left",
                  annotation_font=dict(color=MUTED, size=11))


def status_badge(status: str) -> str:
    """Colored dot + text label (status never shown by color alone)."""
    return (f'<span class="status"><span class="dot" style="background:{STATUS_COLOR[status]}"></span>'
            f'{escape(status)}</span>')


def section(title: str, subtitle: str = ""):
    html(f'<div class="section-title">{escape(title)}</div>'
         + (f'<div class="section-sub">{escape(subtitle)}</div>' if subtitle else ""))


def kpi(col, label: str, value: str, note: str = ""):
    col.markdown(f'<div class="kpi"><div class="kpi-label">{escape(label)}</div>'
                 f'<div class="kpi-value">{escape(value)}</div><div class="kpi-note">{escape(note)}</div></div>',
                 unsafe_allow_html=True)


# ============================================================================ styles
html(f"""<style>
.stApp {{background:{PAGE_BG};}}
.block-container {{padding-top:3.5rem; max-width:1400px;}}
[data-testid="stAppDeployButton"], footer {{display:none;}}
.kicker {{display:flex; align-items:center; gap:14px; color:{BLUE}; letter-spacing:.22em; font-size:14px;
          font-weight:600; text-transform:uppercase;}}
.kicker::before {{content:""; width:46px; height:3px; background:{GOLD};}}
.page-title {{font-size:42px; font-weight:400; color:{INK}; margin:4px 0 18px; line-height:1.15;}}
.page-title b {{color:{BLUE}; font-weight:800;}}
.alert {{background:#fff; border:2px solid #d03b3b; border-radius:14px; padding:20px 26px; margin-bottom:22px;}}
.alert-head {{display:flex; gap:28px; flex-wrap:wrap; align-items:center; margin-bottom:6px;}}
.alert-tag {{color:#d03b3b; font-weight:800; letter-spacing:.18em; font-size:15px;}}
.alert-tag::before {{content:"●"; margin-right:10px;}}
.alert-meta {{color:{GOLD}; font-weight:700; letter-spacing:.16em; font-size:13px; text-transform:uppercase;}}
.alert-headline {{font-size:26px; font-weight:800; color:{INK}; margin:4px 0;}}
.alert-text {{font-size:17px; color:{INK_2}; line-height:1.5;}}
.alert-note {{font-size:13px; color:{MUTED}; margin-top:8px;}}
table.fleet {{width:100%; border-collapse:collapse; background:#fff; font-size:16px;}}
table.fleet th {{background:{BLUE}; color:#fff; text-align:left; padding:12px 14px; font-weight:700;}}
table.fleet td {{padding:11px 14px; border-bottom:1px solid #e6e8ee; color:{INK}; vertical-align:top;
                 white-space:nowrap;}}
table.fleet tr:nth-child(even) td {{background:#EEF2F9;}}
table.fleet td.aircraft {{font-weight:800;}}
table.fleet td.why {{font-size:13px; color:{INK_2}; min-width:260px; white-space:normal;}}
.status {{font-weight:700; white-space:nowrap;}}
.dot {{display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px;}}
.kpi {{background:#fff; border-radius:12px; padding:14px 18px; border:1px solid rgba(11,11,11,.08); height:100%;}}
.kpi-label {{font-size:12px; color:{MUTED}; text-transform:uppercase; letter-spacing:.08em; font-weight:600;}}
.kpi-value {{font-size:28px; font-weight:800; color:{NAVY};}}
.kpi-note {{font-size:12.5px; color:{INK_2};}}
.section-title {{font-size:19px; font-weight:800; color:{NAVY}; margin-top:10px;}}
.section-sub {{font-size:13.5px; color:{INK_2}; margin-bottom:6px;}}
.insight {{background:#fff; border-left:4px solid {GOLD}; border-radius:8px; padding:12px 16px; margin:6px 0 14px;
           color:{INK}; font-size:14.5px;}}
</style>""")


# ============================================================================ data
@st.cache_data(show_spinner="Loading fleet data…")
def load_data() -> fa.FleetData:
    return fa.load_fleet_data()


try:
    data = load_data()
except FileNotFoundError as err:
    st.error(str(err))
    st.stop()

last_date = data.test[config.DATE_COLUMN].max()

with st.sidebar:
    st.markdown("### Settings")
    basis = st.radio("Aircraft status based on",
                     ["Latest screening", "Riskiest screening, last 30 days"],
                     help="Latest = current belt state. Last 30 days = worst screening per aircraft in that window.")
    window_days = None if basis == "Latest screening" else 30
    st.caption(f"Training: {len(data.train):,} screenings, {data.train.month.min():%b %Y}–{data.train.month.max():%b %Y} "
               f"(actual outcomes).  \nTest: {len(data.test):,} screenings, {data.test.month.min():%b %Y}–"
               f"{last_date:%b %Y} (model predictions).")
    st.caption("Associations shown here are not proof of cause. Confirm by physical inspection and a tool "
               "check against a calibrated reference.")

aircraft = fa.aircraft_status(data, window_days)
tools = fa.tool_summary(data)
alert = fa.fleet_alert(aircraft, tools)

tab_alert, tab_trends, tab_factors, tab_tools, tab_inspect, tab_model, tab_agents = st.tabs(
    ["Fleet alert", "Trends", "Factors", "Tools & calibration", "Inspection list", "Model", "AI agents"])

# ============================================================================ 1. Fleet alert (main page)
with tab_alert:
    html('<div class="kicker">Case 3 · Fleet belt health</div>'
         '<div class="page-title">B787 Fleet <b>Dashboard</b></div>')

    html(f"""<div class="alert">
      <div class="alert-head"><span class="alert-tag">FLEET ALERT</span>
        <span class="alert-meta">Data through {last_date:%d %b %Y}</span></div>
      <div class="alert-headline">{escape(alert["headline"])}</div>
      <div class="alert-text">{escape(alert["detail"])} {escape(alert["factor"])}</div>
      <div class="alert-note">Association, not proven cause. Recommended: pull {escape(alert["tool_id"])} for
        calibration and inspect High Risk aircraft first.</div>
    </div>""")

    show_all = st.toggle("Show all 100 aircraft", value=False)
    rows = aircraft if show_all else aircraft[aircraft["Belt Status"] != fa.STATUS_NORMAL]
    body = "".join(
        f'<tr><td class="aircraft">{escape(r.Aircraft)}</td><td>{status_badge(r["Belt Status"])}</td>'
        f'<td>{pct(r["Tension Difference"], signed=True)}</td><td>{escape(r.Tool)}</td>'
        f'<td>{escape(r.Engine)}</td><td>{r["Screening date"]:%d %b %Y}</td><td>{pct(r["Defect risk"] * 100, 0)}</td>'
        f'<td class="why">{escape(r.Why)}</td></tr>'
        for _, r in rows.iterrows())
    html('<table class="fleet"><thead><tr><th>Aircraft</th><th>Belt Status</th><th>Tension Difference</th>'
         '<th>Tool</th><th>Engine</th><th>Screening</th><th>Defect risk</th><th>Why flagged</th></tr></thead>'
         f'<tbody>{body}</tbody></table>')
    st.caption("High Risk = model predicts a confirmed defect. Medium = defect risk ≥ 20% or a measurement outside "
               "the normal range (99% of defect-free screenings). Tension Difference = measured vs target tension.")

    st.write("")
    c1, c2, c3, c4 = st.columns(4)
    status_counts = aircraft["Belt Status"].value_counts()
    kpi(c1, "High Risk aircraft", str(status_counts.get(fa.STATUS_HIGH, 0)), "inspect first")
    kpi(c2, "Medium aircraft", str(status_counts.get(fa.STATUS_MEDIUM, 0)), "inspect at next check")
    kpi(c3, "Predicted defect rate", pct(data.test.predicted_defect.mean() * 100),
        f"test period vs {pct(data.train[config.LABEL_COLUMN].mean() * 100)} in training")
    overdue_tools = tools.loc[tools.current_overdue_share > 0.2, "Tool_ID"].tolist()
    kpi(c4, "Tools overdue for calibration", str(len(overdue_tools)), ", ".join(overdue_tools) or "none")

# ============================================================================ 2. Trends
with tab_trends:
    trend = fa.monthly_defect_trend(data)
    section("Monthly defect rate", "Training months show actual confirmed defects; test months show model predictions.")
    fig = go.Figure()
    for source, color, dash in [("Actual", SERIES_ACTUAL, "solid"), ("Predicted", SERIES_PREDICTED, "dash")]:
        part = trend[trend.source == source]
        fig.add_scatter(x=part.month, y=part.defect_rate * 100, name=source, mode="lines+markers",
                        line=dict(color=color, width=2, dash=dash), marker=dict(size=8, line=dict(color=SURFACE, width=2)),
                        customdata=part.screenings, hovertemplate="%{y:.1f}% of %{customdata} screenings")
    shade_test_period(fig, data)
    st.plotly_chart(style_figure(fig, 340, "%"), width="stretch", config=PLOT_CONFIG)

    yearly = data.train.assign(year=data.train.month.dt.year, m=data.train.month.dt.month)
    # Same spring months a year apart (Apr–May exist in both training years)
    spring = yearly[yearly.m.isin([4, 5])].groupby("year")[config.LABEL_COLUMN].mean() * 100
    html(f'<div class="insight"><b>Two waves a year, and rising.</b> Defects peak in late spring (hottest months) and '
         f'again in autumn when tools run overdue for calibration, then drop after recalibration in December. '
         f'Same months a year apart: Apr–May defect rate rose from {spring.get(2024, float("nan")):.1f}% (2024) to '
         f'{spring.get(2025, float("nan")):.1f}% (2025).</div>')

    left, right = st.columns(2)
    drivers = trend.groupby("month", as_index=False).agg(ambient_temp=("ambient_temp", "mean"),
                                                         overdue_share=("overdue_share", "mean"))
    with left:
        section("Average ambient temperature")
        fig = go.Figure(go.Scatter(x=drivers.month, y=drivers.ambient_temp, mode="lines+markers",
                                   line=dict(color=SERIES_ACTUAL, width=2), marker=dict(size=8),
                                   hovertemplate="%{y:.1f} °C"))
        shade_test_period(fig, data)
        st.plotly_chart(style_figure(fig, 260, " °C", legend=False), width="stretch", config=PLOT_CONFIG)
    with right:
        section("Screenings done with an overdue tool")
        fig = go.Figure(go.Bar(x=drivers.month, y=drivers.overdue_share * 100, marker_color=SERIES_ACTUAL,
                               hovertemplate="%{y:.1f}%"))
        shade_test_period(fig, data)
        st.plotly_chart(style_figure(fig, 260, "%", legend=False), width="stretch", config=PLOT_CONFIG)

# ============================================================================ 3. Factors
with tab_factors:
    section("What goes with a confirmed defect", "Training data (10,000 screenings, actual outcomes).")
    left, right = st.columns(2)
    with left:
        section("Defect rate by tension difference")
        bands = fa.defect_rate_by_tension_band(data.train)
        fig = go.Figure(go.Bar(x=bands.tension_band.astype(str), y=bands.defect_rate * 100, marker_color=SERIES_ACTUAL,
                               customdata=bands.screenings, text=[pct(v * 100) for v in bands.defect_rate],
                               textposition="outside", textfont=dict(color=INK_2),
                               hovertemplate="%{y:.1f}% of %{customdata} screenings<extra></extra>"))
        st.plotly_chart(style_figure(fig, 300, "%", legend=False), width="stretch", config=PLOT_CONFIG)
    with right:
        section("Measurements outside the normal range")
        lift = fa.abnormal_measurement_lift(data.train)
        fig = go.Figure()
        fig.add_bar(y=lift.measurement, x=lift.rate_abnormal * 100, name="Outside normal range", orientation="h",
                    marker_color=SERIES_PREDICTED, hovertemplate="%{x:.1f}%")
        fig.add_bar(y=lift.measurement, x=lift.rate_normal * 100, name="Within normal range", orientation="h",
                    marker_color=SERIES_ACTUAL, hovertemplate="%{x:.1f}%")
        fig.update_layout(hovermode="y unified", yaxis=dict(autorange="reversed"))
        fig = style_figure(fig, 300, "")
        fig.update_xaxes(ticksuffix="%")
        st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
        st.caption("Defect rate (%). " + "; ".join(
            f"{r.measurement}: {r.times_more_likely:.0f}× more likely" for r in lift.itertuples()))

    cols = st.columns(3)
    for col, (column, title) in zip(cols, [("Tool_ID", "By tool"), ("Maintenance_Station", "By station"),
                                           ("Belt_Supplier", "By belt supplier")]):
        with col:
            section(title)
            rates = fa.defect_rate_by(data.train, column)
            fig = go.Figure(go.Bar(x=rates.defect_rate * 100, y=rates[column], orientation="h",
                                   marker_color=SERIES_ACTUAL, customdata=rates.screenings,
                                   hovertemplate="%{x:.1f}% of %{customdata} screenings<extra></extra>"))
            fig.update_layout(yaxis=dict(autorange="reversed"), hovermode="closest")
            fig = style_figure(fig, 280, "", legend=False)
            fig.update_xaxes(ticksuffix="%")
            st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
    html('<div class="insight"><b>Reading this:</b> large tension errors, hot belts and high vibration are the '
         'strongest warning signs. Tool-05, Station C and Supplier B have higher defect rates, but these overlap '
         '(e.g. Tool-05 was the tool most often overdue), so they are associations, not separate proven causes.</div>')

# ============================================================================ 4. Tools & calibration
with tab_tools:
    section("Tool status", f"Latest month = {last_date:%B %Y}. Overdue = calibration load "
                           f"(days × uses since calibration ÷ 1000) above {fa.OVERDUE_CALIBRATION_LOAD}.")
    # Rates as percent numbers so the table can format them
    tool_table = tools.assign(training_rate=tools.training_defect_rate * 100,
                              test_rate=tools.predicted_defect_rate * 100,
                              latest_rate=tools.latest_predicted_rate * 100,
                              overdue_pct=tools.current_overdue_share * 100)
    st.dataframe(
        tool_table[["Tool_ID", "training_rate", "test_rate", "latest_rate", "days_since_calibration",
                    "uses_since_calibration", "latest_tension_error", "overdue_pct"]],
        hide_index=True, width="stretch",
        column_config={
            "Tool_ID": "Tool",
            "training_rate": st.column_config.NumberColumn("Defects (training)", format="%.1f%%"),
            "test_rate": st.column_config.NumberColumn("Predicted (test)", format="%.1f%%"),
            "latest_rate": st.column_config.NumberColumn("Predicted (latest month)", format="%.1f%%"),
            "days_since_calibration": st.column_config.NumberColumn("Days since cal.", format="%d"),
            "uses_since_calibration": st.column_config.NumberColumn("Uses since cal.", format="%d"),
            "latest_tension_error": st.column_config.NumberColumn("Avg tension diff.", format="%+.1f%%"),
            "overdue_pct": st.column_config.NumberColumn("Overdue (test)", format="%.0f%%"),
        })

    left, right = st.columns([1, 2])
    with left:
        section("Defect rate by calibration load", "Training data")
        calib = fa.defect_rate_by_calibration(data.train)
        fig = go.Figure(go.Bar(x=calib.calibration_band.astype(str), y=calib.defect_rate * 100,
                               marker_color=SERIES_ACTUAL, customdata=calib.screenings,
                               text=[pct(v * 100) for v in calib.defect_rate], textposition="outside",
                               textfont=dict(color=INK_2),
                               hovertemplate="%{y:.1f}% of %{customdata} screenings<extra></extra>"))
        st.plotly_chart(style_figure(fig, 300, "%", legend=False), width="stretch", config=PLOT_CONFIG)
    with right:
        tool_ids = tools.Tool_ID.tolist()
        tool_id = st.selectbox("Tool over time", tool_ids, index=tool_ids.index(alert["tool_id"]))
        drift = fa.tool_monthly_drift(data, tool_id)
        sub_left, sub_right = st.columns(2)
        for holder, column, title, suffix in [(sub_left, "days_since_calibration", "Days since calibration", ""),
                                              (sub_right, "tension_error", "Avg tension difference", "%")]:
            with holder:
                section(title)
                fig = go.Figure(go.Scatter(x=drift.month, y=drift[column], mode="lines+markers",
                                           line=dict(color=SERIES_ACTUAL, width=2), marker=dict(size=8),
                                           hovertemplate=f"%{{y:.1f}}{suffix}"))
                shade_test_period(fig, data)
                st.plotly_chart(style_figure(fig, 240, suffix, legend=False), width="stretch", config=PLOT_CONFIG)
    html('<div class="insight"><b>Pattern:</b> when a tool goes long without calibration its belts read high on '
         'tension and defects follow. Tool-05 did this in late 2024, Tool-01 in spring 2025, and Tool-03 now '
         '(not calibrated since early 2025). Other tools stay near target.</div>')

# ============================================================================ 5. Inspection list
with tab_inspect:
    flagged = fa.flagged_screenings(data)
    section("Screenings to inspect", f"{len(flagged)} test-period screenings are High Risk or Medium, "
                                     "highest defect risk first.")
    f1, f2, f3 = st.columns(3)
    status_filter = f1.multiselect("Status", [fa.STATUS_HIGH, fa.STATUS_MEDIUM], [fa.STATUS_HIGH, fa.STATUS_MEDIUM])
    tool_filter = f2.multiselect("Tool", sorted(flagged.Tool_ID.unique()))
    station_filter = f3.multiselect("Station", sorted(flagged.Maintenance_Station.unique()))
    view = flagged[flagged["Belt Status"].isin(status_filter)]
    if tool_filter:
        view = view[view.Tool_ID.isin(tool_filter)]
    if station_filter:
        view = view[view.Maintenance_Station.isin(station_filter)]
    st.dataframe(view.assign(defect_probability=view.defect_probability * 100), hide_index=True, width="stretch",
                 column_config={
                     "Record_ID": "Record", "Aircraft_ID": "Aircraft", "Engine_ID": "Engine",
                     config.DATE_COLUMN: st.column_config.DatetimeColumn("Screening", format="DD MMM YYYY"),
                     "defect_probability": st.column_config.ProgressColumn("Defect risk", format="%.0f%%",
                                                                           min_value=0, max_value=100),
                     "Tension_Dev_Pct": st.column_config.NumberColumn("Tension difference", format="%+.1f%%"),
                     "Tool_ID": "Tool", "Maintenance_Station": "Station", "Why": "Why flagged",
                 })
    st.download_button("Download inspection list (CSV)", view.to_csv(index=False), "inspection_list.csv", "text/csv")

    st.divider()
    section("Aircraft drill-down")
    aircraft_id = st.selectbox("Aircraft", aircraft.Aircraft.tolist())
    history = data.test[data.test.Aircraft_ID == aircraft_id].sort_values(config.DATE_COLUMN)
    history = history.assign(status=history.apply(fa.belt_status, axis=1))
    fig = go.Figure()
    for status in fa.STATUS_ORDER:
        part = history[history.status == status]
        fig.add_scatter(x=part[config.DATE_COLUMN], y=part.defect_probability * 100, mode="markers", name=status,
                        marker=dict(size=11, color=STATUS_COLOR[status], line=dict(color=SURFACE, width=2)),
                        customdata=part[["Tool_ID", "Tension_Dev_Pct", "Engine_ID"]].values,
                        hovertemplate="%{y:.0f}% risk · %{customdata[0]} · tension %{customdata[1]:+.1f}% · "
                                      "%{customdata[2]}<extra>" + status + "</extra>")
    fig.add_hline(y=data.threshold * 100, line=dict(color=MUTED, dash="dot", width=1),
                  annotation_text="Yes threshold", annotation_font_color=MUTED)
    fig.update_layout(hovermode="closest")
    st.plotly_chart(style_figure(fig, 300, "%"), width="stretch", config=PLOT_CONFIG)
    st.caption("Each dot is one screening in the test period; height = predicted defect risk.")

# ============================================================================ 6. Model
with tab_model:
    m = data.oof_metrics
    section("Prediction model", "Average of LightGBM, CatBoost and logistic regression probabilities.")
    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "F1 (cross-validated)", f"{m['F1']:.3f}", "5-fold × 3 repeats, 10,000 rows")
    kpi(c2, "Precision", f"{m['Precision']:.3f}", "flagged screenings that were defects")
    kpi(c3, "Recall", f"{m['Recall']:.3f}", "defects that were flagged")
    kpi(c4, "Yes threshold", f"{data.threshold:.3f}", "lowest within 0.01 F1 of best")
    st.write("")
    st.markdown(
        "- **Inputs:** each screening's own measurements, tool calibration state, 30-day duty summary, "
        "station, tool, supplier and batch. Technician and month were left out (they lowered validation F1).\n"
        "- **Time check:** trained on the first 8,000 screenings by date and scored on the last 2,000: "
        "F1 0.702, precision 0.687, recall 0.719.\n"
        "- **Threshold:** set slightly low to favor catching defects, since the defect rate is trending upward.\n"
        "- **Limits:** synthetic data; associations are not proof of cause; not a certified maintenance tool.")
    submission = config.SUBMISSION_PATH
    if submission.exists():
        st.download_button("Download case_3_predictions.csv", submission.read_bytes(), "case_3_predictions.csv",
                           "text/csv")

# ============================================================================ 7. AI agents
with tab_agents:
    agents_tab.render(data, section)
