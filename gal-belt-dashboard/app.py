"""B787 Engine Belt Defect Investigation: Streamlit UI only. All analysis lives in src/.

Rule: everything shown is computed from the loaded data or produced by user input.
Background, methods and root-cause narrative live in PRESENTATION_NOTES.md, not here.
"""
from __future__ import annotations

import html
import math

import pandas as pd
import streamlit as st

from src import charts as ch
from src import data as data_mod
from src import impact, model, stats
from src.data import FACTOR_LABELS, IDS, NORMAL_STATUS, REQUIRED, SYMPTOMS, load, month_order, summary

st.set_page_config(page_title="B787 Belt Defect Investigation", page_icon="✈️", layout="wide")

def _rgba(hex_colour: str, alpha: float) -> str:
    h = hex_colour.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


# One palette for the whole page: the same constants drive the Plotly charts (src/charts.py), these CSS rules
# and the Streamlit theme (.streamlit/config.toml). All taken from the GAL x MoIAT briefing deck.
_PALETTE = (
    ":root {"
    f"--red:{ch.RED}; --amber:{ch.AMBER}; --green:{ch.GREEN}; --navy:{ch.NAVY}; --gold:{ch.GOLD};"
    f"--red-t:{_rgba(ch.RED, .14)}; --amber-t:{_rgba(ch.AMBER, .18)}; --green-t:{_rgba(ch.GREEN, .14)};"
    f"--navy-t:{_rgba(ch.NAVY, .08)}; --line:{_rgba(ch.GREY, .35)};"
    "}"
)
st.markdown("<style>" + _PALETTE + """
  html, body, [class*="css"] { font-size: 16px; }

  /* Page header in the deck's style: gold rule + small-caps eyebrow, title with one word in navy */
  .eyebrow { display:flex; align-items:center; gap:12px; color:var(--navy); font-size:.85rem; font-weight:600;
             letter-spacing:.08em; text-transform:uppercase; margin:0 0 2px 0; }
  .eyebrow::before { content:""; width:44px; height:2px; background:var(--gold); }
  .deck-title { font-size:2.5rem; font-weight:500; line-height:1.15; margin:0 0 4px 0; }
  .deck-title b { color:var(--navy); font-weight:800; }

  .card { border:1px solid var(--line); border-radius:10px; padding:14px 18px; background:var(--navy-t); color:inherit; }
  .band-High { background:var(--red-t); border:1px solid var(--red); }
  .band-Medium { background:var(--amber-t); border:1px solid var(--amber); }
  .band-Low { background:var(--green-t); border:1px solid var(--green); }
  .band-title { font-size:1.7rem; font-weight:700; margin:0; }

  /* Fleet alert card (deck: white card, red rounded border, soft shadow) */
  .fleet-alert { border:2px solid var(--red); border-radius:12px; padding:20px 26px; margin:4px 0 18px 0;
                 background:transparent; box-shadow:0 6px 18px rgba(0,0,0,0.08); }
  .fleet-alert.ok { border-color:var(--green); }
  .fa-top { display:flex; gap:18px; align-items:baseline; flex-wrap:wrap; margin-bottom:6px; }
  .fa-label { color:var(--red); font-weight:800; letter-spacing:.04em; font-size:1.05rem; }
  .fleet-alert.ok .fa-label { color:var(--green); }
  .fa-tag { color:var(--gold); font-weight:700; letter-spacing:.06em; font-size:.8rem; text-transform:uppercase; }
  .fa-head { font-size:1.55rem; font-weight:800; line-height:1.25; margin:2px 0 6px 0; }
  .fa-sub { font-size:1.08rem; opacity:.85; }
  .fa-evidence { font-size:.88rem; opacity:.65; margin-top:10px; border-top:1px solid var(--line); padding-top:8px; }

  /* Fleet at a glance tiles */
  .tiles { display:flex; flex-wrap:wrap; gap:6px; margin:4px 0 14px 0; }
  .tile { width:54px; padding:6px 0 5px 0; border-radius:7px; text-align:center; font-size:.78rem; font-weight:700;
          border:1px solid var(--line); line-height:1.15; }
  .tile small { display:block; font-weight:500; opacity:.7; font-size:.62rem; }
  .tile.s-High { background:var(--red-t); border-color:var(--red); }
  .tile.s-Medium { background:var(--amber-t); border-color:var(--amber); }
  .tile.s-Normal { background:var(--green-t); border-color:var(--green); }

  /* Fleet status board (deck: navy header, light-blue zebra rows) */
  .board-wrap { max-height:460px; overflow:auto; border-radius:8px; border:1px solid var(--line); }
  table.board { width:100%; min-width:760px; border-collapse:collapse; font-size:.95rem; }
  table.board td, table.board th { white-space:nowrap; }
  table.board thead th { position:sticky; top:0; background:var(--navy); color:#fff; text-align:left;
                         padding:11px 14px; font-weight:700; }
  table.board td { padding:10px 14px; border-top:1px solid var(--line); vertical-align:middle; }
  table.board tbody tr:nth-child(even) td { background:var(--navy-t); }
  .ac { font-weight:800; }
  .dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:7px; vertical-align:middle; }
  .d-High { background:var(--red); } .d-Medium { background:var(--amber); } .d-Normal { background:var(--green); }
  .st { font-weight:700; }
  .chip { display:inline-block; padding:2px 8px; margin:1px 4px 1px 0; border-radius:999px; font-size:.78rem;
          font-weight:600; border:1px solid var(--line); opacity:.75; }
  .chip.bad { background:var(--red-t); border-color:var(--red); color:var(--red); opacity:1; }
  .badge { display:inline-block; margin-left:6px; padding:1px 7px; border-radius:5px; font-size:.72rem;
           font-weight:700; background:var(--amber-t); border:1px solid var(--amber); }
  .why { font-size:.82rem; opacity:.7; }
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
           "confounding": stats.confounding_line(top), "gate": impact.calibration_gate(df),
           "affected": impact.affected_aircraft(df, top), "overall_bayes": stats.bayes_overall(df)}
    out["bayes"] = pd.concat([stats.bayes_rates(df, f).assign(factor_label=FACTOR_LABELS[f])
                              for f in stats.factors_present(df, include_symptoms=False)], ignore_index=True)
    out["strata"] = {by: stats.stratify(df, "Maintenance_Station", by)
                     for by in ["Tool_ID", "Tool_Status"] if by in df.columns}
    out["strat_conclusion"] = stats.stratified_conclusion(df, top)
    out["cmh"] = stats.mantel_haenszel(df, top, "Maintenance_Station") if top else None
    has_two_classes = df["defect"].nunique() == 2
    feats = model.features_for(df)
    out["tree"] = model.fit_tree(df) if feats else None
    out["logit"] = model.fit_logistic(df) if has_two_classes and feats else None
    out["firth"] = model.fit_firth(df) if has_two_classes and feats else None
    out["validation"] = model.validate_pre_job(df)
    out["leakage"] = model.leakage_demo(df) if has_two_classes else None
    return out


# ----------------------------------------------------------------------------- sidebar

with st.sidebar:
    st.header("Data")
    upload = st.file_uploader("Upload maintenance records (CSV or XLSX)", type=["csv", "xlsx"])
    present = st.toggle("Presentation mode", value=False, help="Hides data tables and enlarges charts.")
    st.header("Risk thresholds")
    high_t = st.slider("High risk from", 0, 100, 50, 5, format="%d%%") / 100
    med_t = st.slider("Medium risk from", 0, 100, 20, 5, format="%d%%") / 100
    if med_t > high_t:
        st.warning("Medium threshold is above High; using High for both.")
        med_t = high_t
    with st.expander("Cost assumptions"):
        cost = impact.CostAssumptions(
            cost_per_aog_hour=st.number_input("Cost per AOG hour (USD)", 0.0, 1e6, 10_000.0, 1_000.0),
            aog_hours_per_failure=st.number_input("AOG hours per in-service belt failure", 0.0, 500.0, 24.0, 1.0),
            share_to_in_service=st.slider("Share of defects that would fail in service", 0, 100, 30, 5,
                                          format="%d%%") / 100,
            cost_per_reinspection=st.number_input("Cost per aircraft re-inspection (USD)", 0.0, 1e6, 1_500.0, 100.0),
        )
    st.caption("Prototype. Not for operational aircraft use.")

res = load_cached(upload.getvalue() if upload else None, upload.name if upload else None, str(data_mod.DEFAULT_DATA))

st.markdown('<div class="eyebrow">Case 3 · Find the B787 fleet-wide belt problem</div>'
            '<div class="deck-title">Belt Defect <b>Investigation</b></div>', unsafe_allow_html=True)
if not res.ok:
    if res.missing:
        st.error(f"Missing required columns: **{', '.join(res.missing)}** (required: {', '.join(REQUIRED)}).")
    else:
        st.error("No usable rows: " + "; ".join(x["detail"] for x in res.log))
    st.stop()

df = res.df
A = analyse(df)
top, S = A["top"], A["summary"]
BIG = present
sus = stats.suspect_mask(df, top)
suspect_label = stats.suspect_name(top)
top_level = top["level"] if top else None

_chart_no = [0]


def chart(fig):
    _chart_no[0] += 1  # unique key: two charts with identical content must not collide
    st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False}, key=f"chart_{_chart_no[0]}")


def table(data, **kw):
    if not present:
        st.dataframe(data, width="stretch", hide_index=True, **kw)


def pct(v):
    return "n/a" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.0%}"


# ----------------------------------------------------------------------------- header

st.caption(f"Source: {res.source} · {S['records']} records · {S['aircraft']} aircraft · "
           f"{S['defects']} defects · months: {', '.join(S['months'])}")

# ----------------------------------------------------------------------------- fleet alert + status board

FLEET = impact.fleet_status(df, top)
SYM_PRESENT = [c for c in SYMPTOMS if c in df.columns]
SYM_SHORT = {"Belt_Condition": "Condition", "Belt_Temperature": "Temperature", "Belt_Vibration": "Vibration"}
fleet_type = "B787 " if FLEET["Aircraft_ID"].astype(str).str.upper().str.startswith("B787").all() else ""


def contributing_factor(top: dict | None) -> str:
    if top is None:
        return "No pre-job factor stands out in this data yet."
    where = {"Tool_ID": f"when {stats.suspect_name(top)} is used",
             "Tool_Status": f"when tools in “{top['level']}” status are used",
             "Maintenance_Station": f"at {top['level']}",
             "Month": f"in {top['level']}"}[top["factor"]]
    verb = "are more common" if top["significant"] else "may be more common (not significant after correction)"
    return f"Possible contributing factor: belt defects {verb} {where}."


n_abnormal = int((FLEET["Abnormal_readings"] > 0).sum())
n_high = int((FLEET["Status"] == "High Risk").sum())
if SYM_PRESENT:
    flagged = n_abnormal
    headline = (f"{flagged} {fleet_type}aircraft {'has' if flagged == 1 else 'have'} abnormal belt measurements."
                if flagged else f"No {fleet_type}aircraft have abnormal belt measurements.")
else:
    flagged = n_high
    headline = (f"{flagged} {fleet_type}aircraft {'is' if flagged == 1 else 'are'} at high risk of a belt defect."
                if flagged else f"No {fleet_type}aircraft are at high risk of a belt defect.")
ok_cls = "" if flagged else " ok"
st.markdown(
    f'<div class="fleet-alert{ok_cls}"><div class="fa-top"><span class="fa-label">● FLEET ALERT</span>'
    f'<span class="fa-tag">{html.escape(res.source)} · {S["aircraft"]} aircraft</span></div>'
    f'<div class="fa-head">{html.escape(headline)}</div>'
    f'<div class="fa-sub">{html.escape(contributing_factor(top))}</div>'
    f'<div class="fa-evidence">{html.escape(A["alert"])}</div></div>', unsafe_allow_html=True)

counts = FLEET["Status"].value_counts().reindex(impact.STATUS_ORDER, fill_value=0)
STATUS_KEY = {"High Risk": "High", "Medium": "Medium", "Normal": "Normal"}

st.markdown("##### Fleet at a glance")
tiles = "".join(
    f'<div class="tile s-{STATUS_KEY[r.Status]}" title="{html.escape(str(r.Aircraft_ID))} · {r.Status} · '
    f'{html.escape(str(r.Tool_ID))}">{html.escape(str(r.Aircraft_ID).split("-")[-1])}'
    f'<small>{html.escape(str(r.Tool_ID).replace("Tool-", "T-"))}</small></div>'
    for r in FLEET.sort_values("Aircraft_ID").itertuples())
st.html(f'<div class="tiles">{tiles}</div>')  # data cells, like st.dataframe

options = ["All"] + impact.STATUS_ORDER
pick = st.segmented_control(
    "Show", options, default="All", key="fleet_filter",
    format_func=lambda o: f"All ({len(FLEET)})" if o == "All" else f"● {o} ({counts[o]})") or "All"
board = FLEET if pick == "All" else FLEET[FLEET["Status"] == pick]


def readings_html(r) -> str:
    chips = []
    for c in SYM_PRESENT:
        val = str(r[c])
        bad = val in impact.ABNORMAL_VALUES
        chips.append(f'<span class="chip{" bad" if bad else ""}" title="{SYM_SHORT[c]}: {html.escape(val)}">'
                     f'{SYM_SHORT[c]}{": " + html.escape(val) if bad else ""}</span>')
    return "".join(chips) or '<span class="why">not recorded</span>'


def why_text(r) -> str:
    if r["Defect"] == "Yes":
        return "Defect recorded"
    if r["Abnormal_readings"] >= 2:
        return f"{r['Abnormal_readings']} abnormal readings"
    if r["Abnormal_readings"] == 1:
        return "1 abnormal reading"
    if r["Suspect"]:
        return f"Serviced with suspect factor ({html.escape(str(top['level']))})"
    if r["Tool_Status"] != NORMAL_STATUS:
        return "Tool not in Normal status"
    return "All readings normal"


head_cells = ["Aircraft", "Belt Status"] + (["Belt Readings"] if SYM_PRESENT else []) + ["Tool", "Station", "Month"]
rows_html = []
for _, r in board.iterrows():
    key = STATUS_KEY[r["Status"]]
    badge = (f'<span class="badge">{html.escape(str(r["Tool_Status"]))}</span>'
             if r["Tool_Status"] != NORMAL_STATUS else "")
    cells = [f'<td class="ac">{html.escape(str(r["Aircraft_ID"]))}</td>',
             f'<td><span class="dot d-{key}"></span><span class="st">{r["Status"]}</span>'
             f'<br><span class="why">{why_text(r)}</span></td>']
    if SYM_PRESENT:
        cells.append(f"<td>{readings_html(r)}</td>")
    cells += [f'<td>{html.escape(str(r["Tool_ID"]))}{badge}</td>',
              f'<td>{html.escape(str(r["Station"]))}</td>', f'<td>{html.escape(str(r["Month"]))}</td>']
    rows_html.append("<tr>" + "".join(cells) + "</tr>")
st.html(
    '<div class="board-wrap"><table class="board"><thead><tr>'
    + "".join(f"<th>{h}</th>" for h in head_cells) + "</tr></thead><tbody>"
    + ("".join(rows_html) or f'<tr><td colspan="{len(head_cells)}">No aircraft in this group.</td></tr>')
    + "</tbody></table></div>")
st.caption("Belt Status: High Risk = defect recorded or 2+ abnormal readings · Medium = 1 abnormal reading, "
           "or serviced with the suspect factor or a tool not in Normal status · Normal = everything else.")
st.write("")

others = df[~sus]
k = st.columns(5)
k[0].metric("Overall defect rate", pct(df["defect"].mean()), help=f"{S['defects']} of {S['records']} jobs")
k[1].metric(f"Defect rate with {top_level}" if top else "Defect rate, top factor",
            pct(df.loc[sus, "defect"].mean()) if sus.any() else "n/a",
            help=f"{int(df.loc[sus, 'defect'].sum())} of {int(sus.sum())} jobs")
k[2].metric(f"Defect rate without {top_level}" if top else "Defect rate, other jobs",
            pct(others["defect"].mean()) if len(others) else "n/a",
            help=f"{int(others['defect'].sum())} of {len(others)} jobs")
k[3].metric("Tools needing calibration", df.loc[df["Tool_Status"] != NORMAL_STATUS, "Tool_ID"].nunique())
k[4].metric("Aircraft requiring follow-up", A["affected"]["Aircraft_ID"].nunique())

tabs = st.tabs(["Overview", "Why", "When", "Causation", "Prediction", "Action plan", "Data quality"])


# ----------------------------------------------------------------------------- 1. Overview

def style_records(d: pd.DataFrame):
    def row_style(r):
        # Translucent tints (no fixed text colour) stay readable in light and dark theme.
        return [f"background-color:{_rgba(ch.RED, .14)}" if r.get("Belt_Defect") == "Yes" else ""] * len(r)

    def cell(v):
        if isinstance(v, str) and v not in ("", NORMAL_STATUS) and v in set(df["Tool_Status"]):
            return f"background-color:{_rgba(ch.AMBER, .25)}; font-weight:600"
        if v in ("Abnormal", "High"):
            return f"color:{ch.RED}; font-weight:600"
        return ""

    return d.style.apply(row_style, axis=1).map(cell)


with tabs[0]:
    c1, c2 = st.columns(2)
    rates = stats.rates_by_factor(df, "Tool_ID")
    with c1:
        worst = rates.sort_values(["rate", "jobs"], ascending=False).iloc[0]
        if S["defects"] and (rates.loc[rates["level"] != worst["level"], "defects"] == 0).all():
            title = f"All {S['defects']} defects occurred with {worst['level']}"
        elif S["defects"]:
            title = f"{worst['level']} has the highest defect rate ({worst['defects']} of {worst['jobs']} jobs)"
        else:
            title = f"No defects in {S['records']} jobs"
        hl = worst["level"] if S["defects"] else None
        chart(ch.rate_bar(rates, title, "Tool", hl, BIG))
    with c2:
        p = stats.pareto(df, "Tool_ID")
        if S["defects"]:
            lead = p.iloc[0]
            ptitle = (f"{lead['level']} accounts for {lead['defects'] / S['defects']:.0%} of defects "
                      f"({lead['defects']} of {S['defects']})")
        else:
            ptitle = f"No defects in {S['records']} jobs"
        chart(ch.pareto_chart(p, ptitle, BIG))

    if not present:
        f1, f2, f3, f4 = st.columns(4)
        sel_tool = f1.multiselect("Tool", sorted(df["Tool_ID"].unique()))
        sel_station = f2.multiselect("Station", sorted(df["Maintenance_Station"].unique()))
        sel_month = f3.multiselect("Month", month_order(df["Month"].unique()))
        sel_def = f4.multiselect("Defect", sorted(df["Belt_Defect"].unique()))
        view = df.drop(columns="defect")
        for col, sel in [("Tool_ID", sel_tool), ("Maintenance_Station", sel_station), ("Month", sel_month),
                         ("Belt_Defect", sel_def)]:
            if sel:
                view = view[view[col].isin(sel)]
        st.caption(f"{len(view)} of {len(df)} records · {int((view['Belt_Defect'] == 'Yes').sum())} defects")
        st.dataframe(style_records(view), width="stretch", hide_index=True)


# ----------------------------------------------------------------------------- 2. Why

with tabs[1]:
    rk = A["ranking"]
    if rk.empty:
        st.info(f"No factor varies enough to compare ({S['records']} records).")
    else:
        rk = rk[rk["rate"] >= rk["rate_rest"]] if (rk["rate"] > rk["rate_rest"]).any() else rk
        sig = rk[rk["q_bh"] < stats.ALPHA]
        st.subheader(f"{len(sig)} of {len(A['ranking'])} factor levels significant after correction (q < {stats.ALPHA})")
        show = pd.DataFrame({
            "Factor": rk["factor"].map(FACTOR_LABELS), "Level": rk["level"], "Role": rk["role"],
            "Defects / jobs": [f"{d} / {n}" for d, n in zip(rk["defects"], rk["jobs"])],
            "Defect rate": rk["rate"], "Rate elsewhere": rk["rate_rest"],
            "Relative risk": [("∞" if math.isinf(v) else "–" if math.isnan(v) else f"{v:.1f}×")
                              for v in rk["relative_risk"]],
            "Fisher p": rk["p_fisher"].map(stats.fmt_p), "BH q": rk["q_bh"].map(stats.fmt_p),
            "Cramér's V": rk["cramers_v"].round(2)})
        table(show, column_config={
            "Defect rate": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
            "Rate elsewhere": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1)})

    assoc = A["assoc"]
    table(pd.DataFrame({
        "Factor": assoc["factor"].map(FACTOR_LABELS), "Role": assoc["role"], "Groups": assoc["levels"],
        "Chi-square p": assoc["p_chi2"].map(stats.fmt_p), "Exact p": assoc["p_exact"].map(stats.fmt_p),
        "Cramér's V": assoc["cramers_v"].round(2)}))
    small = [FACTOR_LABELS[r.factor] for r in assoc.itertuples() if r.exact_method]
    if small:
        st.caption(f"Expected counts below 5 for {', '.join(small)}: exact p-value used.")

    b = A["bayes"]
    ob = A["overall_bayes"]
    stand_out = b[b["ci_low"] > ob["post_mean"]]
    btitle = (f"{' / '.join(stand_out['level'].astype(str))}: 90% interval entirely above the fleet average "
              f"({ob['post_mean']:.0%})" if len(stand_out)
              else f"No group's 90% interval sits entirely above the fleet average ({ob['post_mean']:.0%})")
    chart(ch.bayes_chart(b, ob, btitle, BIG))
    bt = b.assign(**{"P(rate above rest)": b["p_higher_than_rest"].map(lambda v: f"{v:.0%}")})
    table(bt[["factor_label", "level", "jobs", "defects", "post_mean", "ci_low", "ci_high",
              "P(rate above rest)"]].rename(columns={
        "factor_label": "Factor", "level": "Level", "jobs": "Jobs", "defects": "Defects",
        "post_mean": "Estimated rate", "ci_low": "90% low", "ci_high": "90% high"}).round(3))

    h1, h2 = st.columns(2)
    defects_ts = df.pivot_table(index="Tool_ID", columns="Maintenance_Station", values="defect", aggfunc="sum",
                                fill_value=0)
    jobs_ts = df.pivot_table(index="Tool_ID", columns="Maintenance_Station", values="defect", aggfunc="count",
                             fill_value=0)
    rows_with_def = defects_ts.index[defects_ts.sum(axis=1) > 0].tolist()
    if len(rows_with_def) == 1:
        n_st = int((defects_ts.loc[rows_with_def[0]] > 0).sum())
        htitle = f"Defects appear only with {rows_with_def[0]}, at {n_st} of {defects_ts.shape[1]} stations"
    else:
        htitle = f"Defects by tool and station ({len(rows_with_def)} tools with defects)"
    stations_per_tool = (jobs_ts > 0).sum(axis=1)
    jtitle = (f"Each tool was used at {stations_per_tool.min()}–{stations_per_tool.max()} stations"
              if stations_per_tool.min() != stations_per_tool.max()
              else f"Each tool was used at {stations_per_tool.min()} stations")
    with h1:
        chart(ch.heatmap(defects_ts, htitle, "Station", "Tool", ch.SEQ_RED, big=BIG,
                         text=defects_ts.map(lambda v: f"{v} defects")))
    with h2:
        chart(ch.heatmap(jobs_ts, jtitle, "Station", "Tool", ch.SEQ_NAVY, big=BIG,
                         text=jobs_ts.map(lambda v: f"{v} jobs")))


# ----------------------------------------------------------------------------- 3. When

with tabs[2]:
    m = A["monthly"]
    tr = A["trend"]
    first, last = m.iloc[0], m.iloc[-1]
    if top and (m["defects"] == m["suspect_defects"]).all() and len(m) > 1:
        mtitle = (f"Defects ({'–'.join(map(str, m['defects']))}) track {top_level} jobs "
                  f"({'–'.join(map(str, m['suspect_jobs']))}) month by month")
    else:
        mtitle = f"Defects per month: {', '.join(f'{r.month} {r.defects}' for r in m.itertuples())}"
    chart(ch.monthly_chart(m, top_level or "top factor", mtitle, BIG))
    table(m.rename(columns={"month": "Month", "jobs": "Jobs", "defects": "Defects", "rate": "Defect rate",
                            "suspect_jobs": f"Jobs with {top_level or 'top factor'}",
                            "suspect_defects": "Defects in those jobs"}),
          column_config={"Defect rate": st.column_config.NumberColumn(format="percent")})

    pc = A["pchart"]
    ptitle = (f"All {len(m)} months inside control limits (centre {pc['centre']:.1%})" if not pc["out_months"]
              else f"{', '.join(pc['out_months'])} outside control limits")
    chart(ch.p_chart_fig(pc, ptitle, BIG))
    st.markdown(f"**p-chart:** {pc['interpretation']}")
    if not math.isnan(tr["z"]):
        st.markdown(f"**Cochran-Armitage trend test:** z = {tr['z']:.2f}, p = {stats.fmt_p(tr['p'])}. "
                    f"{tr['interpretation']}")
    else:
        st.markdown(f"**Cochran-Armitage trend test:** {tr['interpretation']}")


# ----------------------------------------------------------------------------- 4. Causation

with tabs[3]:
    st.markdown(f"**{A['strat_conclusion']}**")
    for by, res_s in A["strata"].items():
        by_label = FACTOR_LABELS[by]
        title = (f"Within each {by_label.lower()}, station defect rates are identical"
                 if (res_s["verdicts"]["rate_spread"] == 0).all()
                 else f"Station rates within each {by_label.lower()} (max spread "
                      f"{res_s['verdicts']['rate_spread'].max():.0%})")
        chart(ch.small_multiples(res_s["table"], "Maintenance_Station", by, title, "Station", by_label, BIG))
        st.markdown(f"{res_s['interpretation']} Crude station p = {stats.fmt_p(res_s['crude_p'])}.")
        table(res_s["verdicts"].rename(columns={"jobs": "Jobs", "rate_spread": "Max − min station rate",
                                                "p": "Within-group p", "effect": "Station effect?"}))
    if A["cmh"] and not math.isnan(A["cmh"]["p"]):
        holds = A["cmh"]["p"] < stats.ALPHA
        st.markdown(f"**Cochran-Mantel-Haenszel** ({top_level} vs other jobs, stratified by station): "
                    f"χ² = {A['cmh']['stat']:.1f}, p = {stats.fmt_p(A['cmh']['p'])}. {top_level} effect "
                    f"{'remains significant' if holds else 'is not significant'} after accounting for station.")
    if A["confounding"]:
        st.warning(A["confounding"])


# ----------------------------------------------------------------------------- 5. Prediction

with tabs[4]:
    if A["logit"] is None:
        st.info(f"No model: {S['defects']} defects in {S['records']} jobs (both outcomes are needed).")
    else:
        lr = A["logit"]
        feats = lr["features"]
        excluded = [c for c in SYMPTOMS + IDS if c in df.columns]
        st.subheader("Pre-job risk check")
        st.caption(f"Inputs: {', '.join(FACTOR_LABELS[f] for f in feats)} · "
                   f"not used: {', '.join(FACTOR_LABELS.get(c, c) for c in excluded)}")
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
            bayes_txt = (f"<br>Tool status <b>{job.get('Tool_Status')}</b>: {int(bb['defects'])} of "
                         f"{int(bb['jobs'])} past jobs defective · estimated rate {bb['post_mean']:.0%} "
                         f"(90% interval {bb['ci_low']:.0%}–{bb['ci_high']:.0%})")
        st.markdown(
            f'<div class="card band-{res_c["band"]}"><p class="band-title">{icon} {res_c["band"]} risk · '
            f'{res_c["probability"]:.0%}</p><b>Main reason:</b> {res_c["reason"]}{bayes_txt}'
            f'<br><b>Recommendation:</b> {res_c["recommendation"]}</div>', unsafe_allow_html=True)
        if "Tool_ID" in job and "Tool_Status" in job:
            seen = int(((df["Tool_ID"] == job["Tool_ID"]) & (df["Tool_Status"] == job["Tool_Status"])).sum())
            if seen == 0:
                st.caption(f"⚠️ {job['Tool_ID']} with status '{job['Tool_Status']}' occurs in 0 of "
                           f"{S['records']} records: this score is extrapolated.")

        st.subheader(f"Decision tree rule (learned from {S['records']} jobs)")
        t1, t2 = st.columns(2)
        with t1:
            for rule in A["tree"]["english"]:
                st.markdown(f"- {rule}")
            st.graphviz_chart(A["tree"]["dot"], width="stretch")
        with t2:
            coef = lr["coefficients"].head(8)
            table(coef.assign(coefficient=coef["coefficient"].round(2),
                              odds_multiplier=coef["odds_multiplier"].round(2)).rename(columns={
                "factor": "Factor", "level": "Level", "coefficient": "L2 logistic coefficient",
                "odds_multiplier": "Odds multiplier"}))
            fi = A["firth"]
            if fi is not None:
                ft = fi["coefficients"]
                # Only risk-raising terms, strongest first
                ft = ft[(ft["term"] != "(intercept)") & (ft["odds_multiplier"] > 1.5)]
                ft = ft.sort_values("coefficient", ascending=False).head(3)
                ft = ft.assign(term=ft["term"].map(lambda t: next(
                    (f"{FACTOR_LABELS[f]} = {t[len(f) + 1:]}" for f in FACTOR_LABELS if t.startswith(f + "_")), t)))
                effects = "; ".join(f"{t} ×{o:.0f} odds" if o >= 10 else f"{t} ×{o:.1f} odds"
                                    for t, o in zip(ft["term"], ft["odds_multiplier"])) or "no term raises odds above ×1.5"
                st.markdown(f"**Firth logistic ({'converged' if fi['converged'] else 'not converged'}):** {effects}")
        chart(ch.risk_probs_chart(lr["fitted"], high_t, med_t, BIG))

        val = A["validation"]
        st.subheader(f"Leave-one-out validation ({S['defects']} defects, {S['records'] - S['defects']} non-defects)")
        mcols = st.columns(2)
        for col, name, key in [(mcols[0], "Logistic regression", "logistic"), (mcols[1], "Decision tree", "tree")]:
            v = val[key]
            with col:
                st.markdown(f"**{name}**")
                if v["loo"] is None:
                    st.info(" ".join(v["warnings"]))
                    continue
                mm = st.columns(3)
                mm[0].metric("ROC-AUC", f"{v['loo']['auc']:.2f}")
                mm[1].metric("Recall", f"{v['loo']['recall']:.0%}")
                mm[2].metric("Precision", f"{v['loo']['precision']:.0%}")
                if v["kfold"]:
                    st.caption(f"Stratified {v['kfold']['k']}-fold: AUC {v['kfold']['auc']:.2f}, "
                               f"recall {v['kfold']['recall']:.0%}, precision {v['kfold']['precision']:.0%}")
                chart(ch.confusion_fig(v["loo"]["confusion"], f"{name}: {v['loo']['tp']} of "
                                       f"{v['loo']['tp'] + v['loo']['fn']} defects caught", BIG))
        for w in val["logistic"]["warnings"]:
            st.warning(w)

        lk = A["leakage"]
        if lk and lk["validation"]["loo"] and val["logistic"]["loo"]:
            pre, sym = val["logistic"]["loo"], lk["validation"]["loo"]
            st.subheader("Leakage comparison")
            table(pd.DataFrame([
                {"Model": "Pre-job inputs", "Inputs": ", ".join(FACTOR_LABELS[f] for f in feats),
                 "AUC": round(pre["auc"], 2), "Recall": f"{pre['recall']:.0%}", "Precision": f"{pre['precision']:.0%}"},
                {"Model": "Symptom inputs", "Inputs": ", ".join(FACTOR_LABELS[f] for f in lk["features"]),
                 "AUC": round(sym["auc"], 2), "Recall": f"{sym['recall']:.0%}", "Precision": f"{sym['precision']:.0%}"},
            ]))
            if present:
                st.markdown(f"Symptom model AUC {sym['auc']:.2f} vs pre-job model AUC {pre['auc']:.2f}.")


# ----------------------------------------------------------------------------- 6. Action plan

with tabs[5]:
    aff = A["affected"]
    n_air = aff["Aircraft_ID"].nunique() if not aff.empty else 0
    if aff.empty:
        st.subheader(f"0 of {S['aircraft']} aircraft need follow-up")
    else:
        n_high = int(aff["Priority"].str.startswith("1").sum())
        st.subheader(f"{n_air} of {S['aircraft']} aircraft need follow-up ({n_high} high priority)")
        st.dataframe(aff, width="stretch", hide_index=True)
        st.download_button("Download inspection list (CSV)", aff.to_csv(index=False).encode(),
                           "aircraft_inspection_list.csv", "text/csv", icon=":material/download:")

    g = A["gate"]
    gc1, gc2 = st.columns([3, 2])
    with gc1:
        chart(ch.gate_chart(g, BIG))
    with gc2:
        st.metric("Defects avoided", f"{g['defects_avoided']} of {g['defects_total']}")
        st.metric("Reduction", f"{g['reduction_pct']:.0f}%")
        st.metric("Jobs that would need a different tool", f"{g['jobs_blocked']} of {g['jobs_total']}")

    ce = impact.cost_estimate(g["defects_avoided"], n_air, cost)
    st.subheader(f"Estimated net benefit over {len(S['months'])} months: ${ce['net_benefit']:,.0f}")
    cc = st.columns(4)
    cc[0].metric("In-service failures avoided", f"{ce['in_service_failures_avoided']:.1f}")
    cc[1].metric("AOG hours avoided", f"{ce['aog_hours_avoided']:.0f} h")
    cc[2].metric("AOG cost avoided", f"${ce['aog_cost_avoided']:,.0f}")
    cc[3].metric("Re-inspection cost", f"${ce['reinspection_cost']:,.0f}")
    st.caption(f"{g['defects_avoided']} defects × {cost.share_to_in_service:.0%} × {cost.aog_hours_per_failure:.0f} h "
               f"× ${cost.cost_per_aog_hour:,.0f}/h − {n_air} re-inspections × ${cost.cost_per_reinspection:,.0f} "
               "(sidebar assumptions)")


# ----------------------------------------------------------------------------- 7. Data quality

with tabs[6]:
    st.dataframe(pd.DataFrame(res.log).rename(columns={"step": "Step", "detail": "Detail"}), width="stretch",
                 hide_index=True)
    profile = pd.DataFrame([{"Column": c, "Distinct values": int(df[c].nunique()),
                             "Values": ", ".join(map(str, month_order(df[c].unique()) if c == "Month"
                                                     else sorted(df[c].unique())))[:120]}
                            for c in df.columns if c not in IDS + ["defect"]])
    st.dataframe(profile, width="stretch", hide_index=True)
