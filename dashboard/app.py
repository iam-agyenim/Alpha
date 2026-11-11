"""B787 fleet belt health (GAL Case 3): a minimal findings dashboard and an agentic maintenance workflow.

Run from the project root:
    .venv/bin/streamlit run dashboard/app.py
Needs model outputs first: .venv/bin/python scripts/train_and_predict.py
"""
import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make belt_defect importable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import report_share as share  # noqa: E402  (dashboard/report_share.py)
import workflow_view  # noqa: E402  (dashboard/workflow_view.py)
from belt_defect import config
from belt_defect import fleet_analysis as fa
from belt_defect.agents import settings
from belt_defect.agents import workflow as wf

st.set_page_config(page_title="B787 Belt Health", page_icon="✈️", layout="wide")

# --- Three-colour theme: white, green, black (greys are tints of black) ---
GREEN, GREEN_TINT, GREEN_MID, BLACK = "#0B6B3A", "#E8F3EC", "#9CCBB0", "#0B0B0B"
INK_2, MUTED, LINE = "#4A4F4C", "#8A918D", "#E3E7E4"
PLOT = {"displayModeBar": False}
RUNS_DIR = config.OUTPUT_DIR / "workflow_runs"
SAMPLE_RUN = RUNS_DIR / "sample_run.json"


def html(markup: str):
    st.markdown(markup, unsafe_allow_html=True)


html(f"""<style>
.stApp {{background:#FFFFFF;}}
.block-container {{padding-top:2rem; max-width:1500px;}}
[data-testid="stAppDeployButton"], footer {{display:none;}}
[data-testid="stSidebar"] {{background:#FFFFFF; border-right:1px solid {LINE};}}
h1,h2,h3 {{color:{BLACK};}}
.stButton > button, .stDownloadButton > button, .stLinkButton > a {{border-radius:8px; font-weight:600;}}
.stButton > button[kind="primary"], .stDownloadButton > button {{background:{BLACK}; color:#fff; border:1px solid {BLACK};}}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {{background:#2A2D2B; color:#fff; border-color:#2A2D2B;}}
.stButton > button[kind="secondary"], .stLinkButton > a {{background:#fff; color:{BLACK}; border:1px solid {BLACK};}}
.kicker {{display:flex; align-items:center; gap:12px; color:{GREEN}; letter-spacing:.2em; font-size:12.5px; font-weight:700;
          text-transform:uppercase;}}
.kicker::before {{content:""; width:36px; height:3px; background:{GREEN};}}
.title {{font-size:34px; font-weight:400; color:{BLACK}; margin:2px 0 14px;}} .title b {{font-weight:800;}}
.kpi {{border:1px solid {LINE}; border-radius:14px; padding:14px 18px; background:#fff; height:100%;}}
.kpi .l {{font-size:11.5px; color:{MUTED}; text-transform:uppercase; letter-spacing:.08em; font-weight:600;}}
.kpi .v {{font-size:30px; font-weight:800; color:{BLACK}; line-height:1.15;}} .kpi .v span {{font-size:15px; color:{MUTED}; font-weight:500;}}
.kpi .n {{font-size:12.5px; color:{INK_2};}}
.kpi.accent {{border-color:{GREEN}; background:{GREEN_TINT};}} .kpi.accent .v {{color:{GREEN};}}
.alert {{border:1.5px solid {BLACK}; border-radius:14px; padding:16px 20px; margin:14px 0 6px; background:#fff;}}
.alert .h {{font-size:20px; font-weight:800; color:{BLACK};}} .alert .t {{font-size:15px; color:{INK_2}; margin-top:4px; line-height:1.5;}}
.alert .tag {{display:inline-block; background:{BLACK}; color:#fff; font-size:11px; font-weight:700; letter-spacing:.12em;
             border-radius:6px; padding:3px 8px; margin-bottom:8px;}}
.alert .act {{margin-top:10px; font-size:14px; color:{GREEN}; font-weight:700;}}
.sec {{font-size:16px; font-weight:800; color:{BLACK}; margin:16px 0 2px;}} .secsub {{font-size:12.5px; color:{MUTED}; margin-bottom:6px;}}
table.t {{width:100%; border-collapse:collapse; font-size:14px;}}
table.t th {{text-align:left; font-size:11.5px; color:{MUTED}; text-transform:uppercase; letter-spacing:.06em; font-weight:600;
            padding:8px 10px; border-bottom:1px solid {LINE};}}
table.t td {{padding:9px 10px; border-bottom:1px solid #F0F2F1; color:{BLACK}; vertical-align:top; white-space:nowrap;}}
table.t td.why {{font-size:12.5px; color:{INK_2}; white-space:normal; min-width:220px;}} table.t td.ac {{font-weight:700; white-space:nowrap;}}
.wrap {{overflow-x:auto;}}
.badge {{display:inline-block; font-size:11.5px; font-weight:700; border-radius:999px; padding:2px 10px; white-space:nowrap;}}
.badge.high {{background:{BLACK}; color:#fff;}} .badge.medium {{border:1.5px solid {GREEN}; color:{GREEN};}}
.badge.normal {{background:{GREEN_TINT}; color:{GREEN};}}
.note {{font-size:12.5px; color:{MUTED};}}
.st-key-page [role="radiogroup"] {{gap:2px;}}
.st-key-page [data-testid="stRadioOption"] {{padding:9px 12px; border-radius:8px; width:100%; cursor:pointer;}}
.st-key-page [data-testid="stRadioOption"] > div > div:first-child:not([data-testid]) {{display:none;}}
.st-key-page [data-testid="stRadioOption"] p {{font-size:15px;}}
.st-key-page [data-testid="stRadioOption"]:hover {{background:#F3F5F4;}}
.st-key-page [data-testid="stRadioOption"][data-selected="true"] {{background:{GREEN_TINT}; box-shadow:inset 3px 0 0 {GREEN};}}
.st-key-page [data-testid="stRadioOption"][data-selected="true"] p {{font-weight:700; color:{GREEN};}}
.appr {{border:1.5px dashed {GREEN}; border-radius:14px; padding:16px 20px; background:{GREEN_TINT};}}
.appr .h {{font-size:17px; font-weight:800; color:{BLACK};}} .appr .t {{font-size:14px; color:{INK_2}; margin-top:4px;}}
.facts {{display:flex; gap:10px; flex-wrap:wrap; margin:10px 0 4px;}}
.fact {{background:#fff; border:1px solid {LINE}; border-radius:10px; padding:6px 12px; font-size:13px;}} .fact b {{font-size:16px;}}
</style>""")


def badge(status: str) -> str:
    cls = {fa.STATUS_HIGH: "high", fa.STATUS_MEDIUM: "medium"}.get(status, "normal")
    return f'<span class="badge {cls}">{escape(status)}</span>'


def kpi(col, label, value, note="", accent=False):
    col.markdown(f'<div class="kpi{" accent" if accent else ""}"><div class="l">{escape(label)}</div>'
                 f'<div class="v">{value}</div><div class="n">{escape(note)}</div></div>', unsafe_allow_html=True)


def section(title, sub=""):
    html(f'<div class="sec">{escape(title)}</div>' + (f'<div class="secsub">{escape(sub)}</div>' if sub else ""))


def style_fig(fig, height=270, suffix="%"):
    fig.update_layout(height=height, margin=dict(l=4, r=8, t=8, b=4), paper_bgcolor="#fff", plot_bgcolor="#fff",
                      font=dict(family="Inter, system-ui, sans-serif", color=INK_2, size=12), showlegend=False,
                      hoverlabel=dict(bgcolor="#fff", bordercolor=LINE, font_color=BLACK), bargap=0.35,
                      barcornerradius=4)
    fig.update_xaxes(showgrid=False, linecolor=LINE, tickfont=dict(color=MUTED), title=None)
    fig.update_yaxes(gridcolor="#EEF1EF", zeroline=False, tickfont=dict(color=MUTED), title=None, ticksuffix=suffix)
    return fig


# ============================================================================ data
@st.cache_data(show_spinner="Loading fleet data…")
def load_data() -> fa.FleetData:
    return fa.load_fleet_data()


try:
    data = load_data()
except FileNotFoundError as err:
    st.error(str(err))
    st.stop()

with st.sidebar:
    html(f'<div style="font-weight:800;font-size:17px;color:{BLACK};margin:4px 0 12px">✈️ B787 Belt Health</div>')
    page = st.radio("Pages", ["Dashboard", "Workflow"], key="page", label_visibility="collapsed",
                    format_func=lambda p: {"Dashboard": "📊  Dashboard", "Workflow": "🔀  Workflow"}[p])
    st.divider()
    st.caption(f"Training: {len(data.train):,} screenings with known outcomes, {data.train.month.min():%b %Y}–"
               f"{data.train.month.max():%b %Y}.  \nLatest period: {len(data.test):,} screenings scored by the model, "
               f"{data.test.month.min():%b %Y}–{data.test.month.max():%b %Y}.")
    st.caption("Associations are not proof of cause. A qualified engineer makes every maintenance decision.")


# ============================================================================ dashboard
def page_dashboard():
    aircraft = fa.aircraft_status(data)
    tools = fa.tool_summary(data)
    alert = fa.fleet_alert(aircraft, tools)
    m = data.oof_metrics
    n_high = int((aircraft["Belt Status"] == fa.STATUS_HIGH).sum())
    n_flag = int((aircraft["Belt Status"] != fa.STATUS_NORMAL).sum())

    html('<div class="kicker">Case 3 · Fleet belt health</div><div class="title">B787 fleet <b>findings</b></div>')
    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "Aircraft flagged", f"{n_flag}<span> / {len(aircraft)}</span>", "High Risk or Medium, latest screening")
    kpi(c2, "High Risk", f"{n_high}", "model predicts a defect: inspect first", accent=True)
    kpi(c3, "Predicted defects", f"{int(data.test.predicted_defect.sum())}<span> / {len(data.test):,}</span>",
        f"{data.test.predicted_defect.mean():.1%} of latest screenings vs {data.train.is_defect.mean():.1%} historically")
    kpi(c4, "Model F1", f"{m['F1']:.2f}", "0.70 on a strict future-period test")

    html(f'<div class="alert"><span class="tag">FLEET ALERT</span><div class="h">{escape(alert["headline"])} '
         f'{escape(alert["detail"])}</div><div class="t">{escape(alert["factor"])}</div>'
         f'<div class="act">Recommended: pull {escape(alert["tool_id"])} for calibration and inspect High Risk aircraft first. '
         f'<span style="color:{MUTED};font-weight:500">Association, not proven cause.</span></div></div>')

    left, right = st.columns([1.15, 1], gap="large")
    with left:
        section("Aircraft needing attention", "Latest screening per aircraft, highest risk first")
        show_all = st.toggle("Show all 100 aircraft", value=False)
        rows = aircraft if show_all else aircraft[aircraft["Belt Status"] != fa.STATUS_NORMAL]
        body = "".join(
            f'<tr><td class="ac">{escape(r.Aircraft)}</td><td>{badge(r["Belt Status"])}</td>'
            f'<td>{r["Tension Difference"]:+.1f}%</td><td>{escape(r.Tool)}</td><td>{r["Defect risk"]:.0%}</td>'
            f'<td class="why">{escape(r.Why)}</td></tr>' for _, r in rows.iterrows())
        html('<div class="wrap" style="max-height:470px;overflow-y:auto"><table class="t"><thead><tr><th>Aircraft</th>'
             '<th>Status</th><th>Tension</th><th>Tool</th><th>Risk</th><th>Why flagged</th></tr></thead>'
             f'<tbody>{body}</tbody></table></div>')
        html('<div class="note" style="margin-top:6px">High Risk = model predicts a defect. Medium = risk ≥ 20% or a '
             'reading outside the normal range.</div>')
    with right:
        section("Defect rate by month", "Actual outcomes (green) and model predictions for the latest period (black)")
        trend = fa.monthly_defect_trend(data)
        fig = go.Figure()
        for src, color, dash in [("Actual", GREEN, "solid"), ("Predicted", BLACK, "dash")]:
            d = trend[trend.source == src]
            fig.add_scatter(x=d.month, y=d.defect_rate * 100, mode="lines+markers", name=src,
                            line=dict(color=color, width=2.4, dash=dash), marker=dict(size=6, color=color),
                            hovertemplate="%{x|%b %Y}: %{y:.1f}%<extra>" + src + "</extra>")
        st.plotly_chart(style_fig(fig, 250), width="stretch", config=PLOT)

        c1, c2 = st.columns(2)
        with c1:
            section("By tool calibration load", "Overdue (>90) in black")
            cal = fa.defect_rate_by_calibration(data.train)
            fig = go.Figure(go.Bar(x=cal.calibration_band.astype(str), y=cal.defect_rate * 100,
                                   marker_color=[BLACK if "overdue" in str(b) else GREEN for b in cal.calibration_band],
                                   text=[f"{v:.1f}%" for v in cal.defect_rate * 100], textposition="outside",
                                   hovertemplate="%{x}: %{y:.1f}%<extra></extra>"))
            st.plotly_chart(style_fig(fig, 220), width="stretch", config=PLOT)
        with c2:
            section("By tension error", "More than 10% off target in black")
            ten = fa.defect_rate_by_tension_band(data.train)
            fig = go.Figure(go.Bar(x=ten.tension_band.astype(str), y=ten.defect_rate * 100,
                                   marker_color=[BLACK if str(b) == ">10%" else GREEN for b in ten.tension_band],
                                   text=[f"{v:.0f}%" for v in ten.defect_rate * 100], textposition="outside",
                                   hovertemplate="%{x}: %{y:.1f}%<extra></extra>"))
            st.plotly_chart(style_fig(fig, 220), width="stretch", config=PLOT)

    section("Reports")
    c1, c2, c3 = st.columns([1, 1, 2])
    flagged = fa.flagged_screenings(data)
    c1.download_button("⬇ Inspection list (CSV)", flagged.to_csv(index=False).encode(), "inspection_list.csv",
                       "text/csv", width="stretch")
    if config.SUBMISSION_PATH.exists():
        c2.download_button("⬇ Model predictions (CSV)", config.SUBMISSION_PATH.read_bytes(), "case_3_predictions.csv",
                           "text/csv", width="stretch")
    c3.markdown(f'<div class="note">Model: average of LightGBM, CatBoost and logistic regression · cross-validated '
                f'F1 {m["F1"]:.3f}, precision {m["Precision"]:.3f}, recall {m["Recall"]:.3f} · {len(flagged)} '
                f'screenings in the inspection list.</div>', unsafe_allow_html=True)


# ============================================================================ workflow
def _load_sample():
    if "wf_run" not in st.session_state and SAMPLE_RUN.exists():
        st.session_state.wf_run = wf.WorkflowRun.from_json(SAMPLE_RUN.read_text())
        st.session_state.wf_is_sample = True
        st.session_state.wf_play = f"sample-{st.session_state.wf_run.run_id}"
        st.session_state.wf_start = 0


def _save_run(run):
    try:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        (RUNS_DIR / "last_run.json").write_text(run.to_json())
    except OSError:
        pass


def page_workflow():
    st.session_state.setdefault("wf_runs_used", 0)
    _load_sample()
    html('<div class="kicker">Applied AI workflow</div><div class="title">Belt-defect <b>maintenance workflow</b></div>')
    html('<div class="note" style="margin:-6px 0 12px;font-size:13.5px">Screenings flow through a security agent and '
         'the ML model; Quality & Safety, Logistics and Commercial agents pass results to each other; a security check '
         'verifies every number; a person approves before anything is actioned.</div>')

    key = settings.load_api_key(st.secrets)
    c1, c2, c3, c4 = st.columns([1.3, 1, 1, 2.2])
    batch = c1.selectbox("Batch", list(wf.BATCHES), label_visibility="collapsed")
    runs_left = settings.MAX_BRIEFINGS_PER_SESSION - st.session_state.wf_runs_used
    run_clicked = c2.button("▶ Run workflow", type="primary", width="stretch", disabled=not key or runs_left <= 0,
                            help="Runs the real agents (about a minute, about $0.02).")
    if c3.button("↺ Replay", width="stretch", help="Replay the animation of the current run (no AI cost)."):
        st.session_state.wf_play = f"replay-{pd.Timestamp.now().value}"
        st.session_state.wf_start = 0
    run = st.session_state.get("wf_run")
    caption = c4.empty()

    if run_clicked:
        lines = []
        with st.status("Workflow running: agents are passing data to each other…", expanded=True) as status:
            box = st.empty()

            def on_event(e):
                lines.append(f"`{e['t'][11:19]}` **{e['agent']}** · {e['message']}")
                box.markdown("  \n".join(lines[-14:]))

            run = wf.run_workflow(wf.make_client(key), data, batch, on_event=on_event)
            status.update(label=f"Workflow finished · waiting for approval · {run.meter['tokens']:,} tokens · "
                                f"${run.meter['usd']:.3f}", state="complete", expanded=False)
        st.session_state.update(wf_run=run, wf_is_sample=False, wf_play=f"run-{run.run_id}", wf_start=0)
        st.session_state.wf_runs_used += 1
        _save_run(run)

    runs_left = settings.MAX_BRIEFINGS_PER_SESSION - st.session_state.wf_runs_used
    if not key:
        caption.caption("No OpenAI key configured: showing the recorded sample run.")
    elif st.session_state.get("wf_is_sample"):
        caption.caption("Showing the recorded sample run. Press ▶ Run workflow for a live run.")
    elif run:
        caption.caption(f"Live run {run.run_id} · {runs_left} run(s) left this session.")
    if not run:
        st.info("No run yet. Add an OpenAI API key and press ▶ Run workflow.")
        return

    workflow_view.render(run, st.session_state.get("wf_play", run.run_id), st.session_state.get("wf_start", 0))
    _approval_and_outputs(run)

    with st.expander("Agent outputs (structured)"):
        for step, label in [("quality", "Quality & Safety"), ("logistics", "Logistics"), ("commercial", "Commercial")]:
            res = run.outputs.get(step) or {}
            st.markdown(f"**{label} agent** · number check: "
                        + ("passed ✓" if res and not res.get("ungrounded") and not res.get("error")
                           else f"review {res.get('ungrounded') or res.get('error')}"))
            st.json(res.get("output") or {}, expanded=False)
    with st.expander("Full event log"):
        log = pd.DataFrame(run.events)[["t", "agent", "kind", "message", "duration_s", "tokens", "usd"]]
        st.dataframe(log, hide_index=True, width="stretch", height=320)
        st.download_button("⬇ Event log (JSON)", json.dumps(run.events, indent=1, default=str),
                           f"run_{run.run_id}_log.json", "application/json")
    with st.expander("🔒 Security controls"):
        st.markdown(
            "- **Security agent (input):** schema, ID formats, value ranges and duplicates checked; rows with "
            "instruction-like text are quarantined before the model or any agent sees them.\n"
            "- **Least privilege:** agents only call read-only tools and calculators (allowlist per agent); no code, "
            "web, file writes or ability to action work orders.\n"
            "- **Security check (output):** every number an agent writes is verified against the model and data.\n"
            "- **Hand-offs are data, not instructions:** agents are told never to obey text inside hand-offs.\n"
            "- **Human gate:** nothing is issued until a person approves; the decision is logged with name and time.\n"
            f"- **Spend limits:** {settings.MAX_TOOL_ROUNDS} tool rounds per agent, "
            f"{settings.MAX_BRIEFINGS_PER_SESSION} runs per session, daily token cap; key in Secrets / `.env` only.\n"
            "- **Assumptions labelled:** belt stock, calibration slots, flight estimates and unit costs are planning "
            "assumptions, flagged as such to the agents and in the report.")


def _approval_and_outputs(run):
    o = run.outputs
    q = (o.get("quality") or {}).get("output") or {}
    lg = (o.get("logistics") or {}).get("output") or {}
    c = (o.get("commercial") or {}).get("output") or {}
    if run.status.get("approval") == "running":
        belts = sum(p.get("belts_to_order", 0) for p in lg.get("parts_plan", []))
        cost = (c.get("cost_summary") or {}).get("action_cost_usd")
        html(f'<div class="appr"><div class="h">Your decision: approve the plan?</div>'
             f'<div class="t">{escape(c.get("recommendation_to_approver", "Review the agents’ plan."))}</div>'
             f'<div class="facts"><span class="fact"><b>{len(q.get("inspections", []))}</b> inspections</span>'
             f'<span class="fact"><b>{len(q.get("tool_actions", []))}</b> tool actions</span>'
             f'<span class="fact"><b>{belts}</b> belts to order</span>'
             + (f'<span class="fact">plan cost <b>${cost:,}</b></span>' if cost is not None else "")
             + '</div></div>')
        c1, c2, c3, c4 = st.columns([1.2, 2, 0.8, 0.8])
        who = c1.text_input("Approver", value="Maintenance manager")
        note = c2.text_input("Comment (optional)", placeholder="Approved; inspect P1 aircraft before first departure")
        if c3.button("✓ Approve", type="primary", width="stretch"):
            idx = len(run.events)
            st.session_state.wf_run = wf.approve_run(run, "Approved", who, note)
            st.session_state.update(wf_play=f"approve-{run.run_id}", wf_start=idx)
            _save_run(run)
            st.rerun()
        if c4.button("✕ Reject", width="stretch"):
            idx = len(run.events)
            st.session_state.wf_run = wf.approve_run(run, "Rejected", who, note)
            st.session_state.update(wf_play=f"reject-{run.run_id}", wf_start=idx)
            st.rerun()
        return

    if run.approval:
        orders = (o.get("outputs") or {}).get("work_orders", [])
        section("Outputs" if orders else "Decision recorded",
                f"{run.approval['decision']} by {run.approval['approver']} at {run.approval['time'][11:19]} UTC")
        if orders:
            st.dataframe(pd.DataFrame(orders), hide_index=True, width="stretch",
                         column_config={"detail": st.column_config.TextColumn(width="large")})
            c1, c2, c3, c4 = st.columns([1, 1, 1.4, 1])
            c1.download_button("⬇ Report (PDF)", share.run_pdf(run), f"workflow_report_{run.run_id}.pdf",
                               "application/pdf", width="stretch")
            c2.download_button("⬇ Work orders (CSV)", share.work_orders_csv(run), f"work_orders_{run.run_id}.csv",
                               "text/csv", width="stretch")
            to = c3.text_input("Email to", placeholder="maintenance.control@company.com", label_visibility="collapsed")
            valid = "@" in to and "." in to.split("@")[-1]
            c4.link_button("✉️ Email plan", share.mailto_link(to, f"Belt workflow {run.run_id}: work orders",
                                                             share.run_text(run)) if valid else "mailto:",
                           disabled=not valid, width="stretch")
            st.caption("Email opens your own mail app with the plan filled in; attach the PDF for the full report.")


# ============================================================================ router
{"Dashboard": page_dashboard, "Workflow": page_workflow}[page]()
