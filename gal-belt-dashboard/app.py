"""B787 Engine Belt Defect Investigation: Streamlit UI only. All analysis lives in src/.

The page answers four questions, one tab each, with one main visual per tab and a one-line computed answer
above it. Rule: everything shown is computed from the loaded data or produced by user input; nothing names a
tool, station, month or number by hand. Supporting statistics and narrative live in PRESENTATION_NOTES.md.
"""
from __future__ import annotations

import html
import math
import os

import pandas as pd
import streamlit as st

from src import charts as ch
from src import data as data_mod
from src import impact, model, stats
from src.data import FACTOR_LABELS, NORMAL_STATUS, REQUIRED, SYMPTOMS, load, summary

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
    f"--line:{_rgba(ch.GREY, .35)}; --navy-t:{_rgba(ch.NAVY, .07)};"
    "}"
)
st.markdown("<style>" + _PALETTE + """
  html, body, [class*="css"] { font-size: 16px; }
  .block-container { padding-top: 3.2rem; padding-bottom: 1rem; }
  [data-testid="stMetric"] { padding: 0; } [data-testid="stMetricValue"] { font-size: 1.9rem; }

  /* Page header in the deck's style: gold rule + small-caps eyebrow, title with one word in navy */
  .eyebrow { display:flex; align-items:center; gap:12px; color:var(--navy); font-size:.82rem; font-weight:600;
             letter-spacing:.08em; text-transform:uppercase; margin:0; }
  .eyebrow::before { content:""; width:44px; height:2px; background:var(--gold); }
  .deck-title { font-size:2rem; font-weight:500; line-height:1.15; margin:0 0 2px 0; }
  .deck-title b { color:var(--navy); font-weight:800; }

  /* Alert banner (deck: white card, red rounded border, soft shadow) */
  .fleet-alert { border:2px solid var(--red); border-radius:12px; padding:10px 22px; margin:2px 0 6px 0;
                 box-shadow:0 6px 18px rgba(0,0,0,0.08); }
  .fleet-alert.ok { border-color:var(--green); }
  .fa-top { display:flex; gap:18px; align-items:baseline; flex-wrap:wrap; }
  .fa-label { color:var(--red); font-weight:800; letter-spacing:.04em; }
  .fleet-alert.ok .fa-label { color:var(--green); }
  .fa-tag { color:var(--gold); font-weight:700; letter-spacing:.06em; font-size:.78rem; text-transform:uppercase; }
  .fa-head { font-size:1.25rem; font-weight:800; line-height:1.25; margin:2px 0 2px 0; }
  .fa-sub { opacity:.85; }
  .fa-evidence { font-size:.88rem; opacity:.7; margin-top:4px; border-top:1px solid var(--line); padding-top:4px; }

  /* One-line computed answer above each tab's main visual */
  .answer { font-size:1.12rem; font-weight:700; margin:2px 0 4px 0; }

  /* Risk checker result */
  .card { border-radius:10px; padding:12px 18px; margin:6px 0 10px 0; }
  .band-High { background:var(--red-t); border:1px solid var(--red); }
  .band-Medium { background:var(--amber-t); border:1px solid var(--amber); }
  .band-Low { background:var(--green-t); border:1px solid var(--green); }
  .band-title { font-size:1.5rem; font-weight:800; margin:0; }

  /* Fleet status board (deck: navy header, light-blue zebra rows, coloured status dots) */
  .board-wrap { max-height:232px; overflow:auto; border-radius:8px; border:1px solid var(--line); margin:2px 0 10px 0; }
  table.board { width:100%; min-width:640px; border-collapse:collapse; font-size:.93rem; }
  table.board td, table.board th { white-space:nowrap; text-align:left; }
  table.board thead th { position:sticky; top:0; z-index:1; background:var(--navy); color:#fff; padding:8px 14px;
                         font-weight:700; }
  table.board td { padding:6px 14px; border-top:1px solid var(--line); }
  table.board tbody tr:nth-child(even) td { background:var(--navy-t); }
  .ac, .st { font-weight:700; }
  .dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:7px; }
  .d-High { background:var(--red); } .d-Medium { background:var(--amber); } .d-Normal { background:var(--green); }
  .chip { display:inline-block; padding:1px 8px; margin-right:4px; border-radius:999px; font-size:.76rem;
          font-weight:600; border:1px solid var(--line); opacity:.7; }
  .chip.bad { background:var(--red-t); border-color:var(--red); color:var(--red); opacity:1; }
  .badge { display:inline-block; margin-left:6px; padding:0 7px; border-radius:5px; font-size:.72rem;
           font-weight:700; background:var(--amber-t); border:1px solid var(--amber); }
  .board-note { font-size:.8rem; opacity:.65; margin:-6px 0 8px 0; }
  td.tbad { color:var(--red); font-weight:700; }
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
           "monthly": stats.monthly_summary(df, top), "pchart": stats.p_chart(df), "trend": stats.cochran_armitage(df),
           "gate": impact.calibration_gate(df), "affected": impact.affected_aircraft(df, top),
           "strat_conclusion": stats.stratified_conclusion(df, top)}
    has_two_classes = df["defect"].nunique() == 2
    feats = model.features_for(df)
    out["tree"] = model.fit_tree(df) if feats else None
    out["logit"] = model.fit_logistic(df) if has_two_classes and feats else None
    out["validation"] = model.validate_pre_job(df)
    out["leakage"] = model.leakage_demo(df) if has_two_classes else None
    return out


# ----------------------------------------------------------------------------- sidebar: upload + thresholds only

with st.sidebar:
    st.header("Data")
    upload = st.file_uploader("Upload maintenance records (CSV or XLSX)", type=["csv", "xlsx"])
    st.header("Risk thresholds")
    high_t = st.slider("High risk from", 0, 100, 50, 5, format="%d%%") / 100
    med_t = st.slider("Medium risk from", 0, 100, 20, 5, format="%d%%") / 100
    if med_t > high_t:
        st.warning("Medium threshold is above High; using High for both.")
        med_t = high_t
    st.caption("Prototype. Not for operational aircraft use.")

# BELT_DATA lets a local run open a file by default (e.g. the GAL test inputs) instead of the bundled sample.
default_path = os.environ.get("BELT_DATA") or str(data_mod.DEFAULT_DATA)
content, name = (upload.getvalue(), upload.name) if upload else (None, default_path)


@st.cache_data(show_spinner=False)
def read_v2(content: bytes | None, name: str):
    """The raw table if this is a release-v2 file (the real GAL Case 3 data), else None."""
    from src import v2
    try:
        raw = v2.read_raw(content if content is not None else name, name)
    except Exception:
        return None
    return raw if v2.is_v2(raw) else None


raw_v2 = read_v2(content, name)
res = None if raw_v2 is not None else load_cached(content, upload.name if upload else None, default_path)

st.markdown('<div class="eyebrow">Case 3 · Find the B787 fleet-wide belt problem</div>'
            '<div class="deck-title">Belt Defect <b>Investigation</b></div>', unsafe_allow_html=True)
if raw_v2 is not None:
    import v2_page
    v2_page.render(raw_v2, os.path.basename(name))
    st.stop()
if not res.ok:
    if res.missing:
        st.error(f"Missing required columns: **{', '.join(res.missing)}** (required: {', '.join(REQUIRED)}).")
    else:
        st.error("No usable rows: " + "; ".join(x["detail"] for x in res.log))
    st.stop()

df = res.df
A = analyse(df)
top, S = A["top"], A["summary"]
sus = stats.suspect_mask(df, top)
top_level = top["level"] if top else None
suspect = stats.suspect_name(top) if top else None

_chart_no = [0]


def chart(fig, height: int = 310):
    _chart_no[0] += 1  # unique key: two charts with identical content must not collide
    fig.update_layout(height=height)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False}, key=f"chart_{_chart_no[0]}")


def answer(text: str):
    st.markdown(f'<div class="answer">{html.escape(text)}</div>', unsafe_allow_html=True)


def pct(v):
    return "n/a" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.0%}"


# ----------------------------------------------------------------------------- header: alert banner + 4 KPIs

FLEET = impact.fleet_status(df, top)
SYM_PRESENT = [c for c in SYMPTOMS if c in df.columns]
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


if SYM_PRESENT:
    flagged = int((FLEET["Abnormal_readings"] > 0).sum())
    headline = (f"{flagged} {fleet_type}aircraft {'has' if flagged == 1 else 'have'} abnormal belt measurements."
                if flagged else f"No {fleet_type}aircraft have abnormal belt measurements.")
else:
    flagged = int((FLEET["Status"] == "High Risk").sum())
    headline = (f"{flagged} {fleet_type}aircraft {'is' if flagged == 1 else 'are'} at high risk of a belt defect."
                if flagged else f"No {fleet_type}aircraft are at high risk of a belt defect.")
st.markdown(
    f'<div class="fleet-alert{"" if flagged else " ok"}"><div class="fa-top"><span class="fa-label">● FLEET ALERT</span>'
    f'<span class="fa-tag">{html.escape(res.source)} · {S["records"]} jobs · {S["aircraft"]} aircraft · '
    f'{html.escape(", ".join(S["months"]))}</span></div>'
    f'<div class="fa-head">{html.escape(headline)}</div>'
    f'<div class="fa-sub">{html.escape(contributing_factor(top))}</div>'
    f'<div class="fa-evidence">{html.escape(A["alert"])}</div></div>', unsafe_allow_html=True)

others = df[~sus]
k = st.columns(4)
k[0].metric("Total jobs", S["records"])
k[1].metric("Defects", S["defects"], help=f"{pct(df['defect'].mean())} of jobs")
k[2].metric(f"Defect rate with {top_level}" if top else "Defect rate, top factor",
            pct(df.loc[sus, "defect"].mean()) if sus.any() else "n/a",
            help=f"{int(df.loc[sus, 'defect'].sum())} of {int(sus.sum())} jobs")
k[3].metric(f"Defect rate without {top_level}" if top else "Defect rate, other jobs",
            pct(others["defect"].mean()) if len(others) else "n/a",
            help=f"{int(others['defect'].sum())} of {len(others)} jobs")


# Fleet status board: one row per aircraft, worst first (status rules: impact.fleet_status). Rendered with st.html
# because its cells are data, like a dataframe, not narrative text.
STATUS_KEY = {"High Risk": "High", "Medium": "Medium", "Normal": "Normal"}
SYM_SHORT = {"Belt_Condition": "Condition", "Belt_Temperature": "Temperature", "Belt_Vibration": "Vibration"}


def _readings(r) -> str:
    chips = []
    for c in SYM_PRESENT:
        val = str(r[c])
        bad = val in impact.ABNORMAL_VALUES
        chips.append(f'<span class="chip{" bad" if bad else ""}">{SYM_SHORT[c]}{": " + html.escape(val) if bad else ""}'
                     "</span>")
    return "".join(chips) or "not recorded"


_head = ["Aircraft", "Belt Status"] + (["Belt Readings"] if SYM_PRESENT else []) + ["Tool"]
_rows = []
for _, r in FLEET.iterrows():
    badge = (f'<span class="badge">{html.escape(str(r["Tool_Status"]))}</span>'
             if r["Tool_Status"] != NORMAL_STATUS else "")
    cells = [f'<td class="ac">{html.escape(str(r["Aircraft_ID"]))}</td>',
             f'<td><span class="dot d-{STATUS_KEY[r["Status"]]}"></span><span class="st">{r["Status"]}</span></td>']
    if SYM_PRESENT:
        cells.append(f"<td>{_readings(r)}</td>")
    cells.append(f'<td>{html.escape(str(r["Tool_ID"]))}{badge}</td>')
    _rows.append("<tr>" + "".join(cells) + "</tr>")
st.html('<div class="board-wrap"><table class="board"><thead><tr>' + "".join(f"<th>{h}</th>" for h in _head)
        + "</tr></thead><tbody>" + "".join(_rows) + "</tbody></table></div>")
_counts = FLEET["Status"].value_counts()
st.markdown(f'<div class="board-note">{len(FLEET)} aircraft, worst first: '
            + " · ".join(f"{_counts.get(s, 0)} {s}" for s in impact.STATUS_ORDER)
            + ". High Risk = defect or 2+ abnormal readings; Medium = 1 abnormal reading or a suspect / "
              "uncalibrated tool.</div>", unsafe_allow_html=True)

tabs = st.tabs(["Why are defects happening?", "When do defects happen?",
                "Can we predict defects before the job?", "What should maintenance do?"])


# ----------------------------------------------------------------------------- 1. Why

with tabs[0]:
    if top is None:
        answer(f"No pre-job factor stands out: {S['defects']} defects in {S['records']} jobs.")
    else:
        answer(f"{suspect} accounts for {top['defects']} of {S['defects']} defects; "
               f"Fisher p = {stats.fmt_p(top['p_fisher'])}.")
    c1, c2 = st.columns(2)
    with c1:
        rates = stats.rates_by_factor(df, "Tool_ID")
        worst = rates.sort_values(["rate", "jobs"], ascending=False).iloc[0]
        chart(ch.rate_bar(rates, "Defect rate by tool", "Tool", worst["level"] if S["defects"] else None))
    with c2:
        defects_ts = df.pivot_table(index="Tool_ID", columns="Maintenance_Station", values="defect",
                                    aggfunc="sum", fill_value=0)
        jobs_ts = df.pivot_table(index="Tool_ID", columns="Maintenance_Station", values="defect",
                                 aggfunc="count", fill_value=0)
        rate_ts = (defects_ts / jobs_ts.where(jobs_ts > 0)).astype(float)
        labels = pd.DataFrame([[f"{defects_ts.loc[t, s]} of {jobs_ts.loc[t, s]}" if jobs_ts.loc[t, s] else "–"
                                for s in jobs_ts.columns] for t in jobs_ts.index],
                              index=jobs_ts.index, columns=jobs_ts.columns)
        chart(ch.heatmap(rate_ts, "Defect rate by tool and station", "Station", "Tool", ch.SEQ_RED, text=labels))
    st.markdown(f"**Is it the station?** {A['strat_conclusion']}")


# ----------------------------------------------------------------------------- 2. When

with tabs[1]:
    m, pc, tr = A["monthly"], A["pchart"], A["trend"]
    unusual = (f"{', '.join(pc['out_months'])} {'is' if len(pc['out_months']) == 1 else 'are'} outside the "
               "p-chart control limits" if pc["out_months"]
               else f"No month is unusual (all {len(m)} inside the p-chart control limits)")
    if math.isnan(tr["p"]):
        trend = "a trend test needs at least two months"
    else:
        trend = (f"the trend test (Cochran-Armitage p = {stats.fmt_p(tr['p'])}) "
                 + ("finds a significant trend" if tr["p"] < stats.ALPHA else "finds no significant trend"))
    answer(f"{unusual}, and {trend}.")
    if top and (m["defects"] == m["suspect_defects"]).all() and len(m) > 1:
        mtitle = (f"Defects ({'–'.join(map(str, m['defects']))}) track {top_level} jobs "
                  f"({'–'.join(map(str, m['suspect_jobs']))}) month by month")
    else:
        mtitle = f"Defects per month: {', '.join(f'{r.month} {r.defects}' for r in m.itertuples())}"
    chart(ch.monthly_chart(m, top_level or "top factor", mtitle), height=380)


# ----------------------------------------------------------------------------- 3. Predict

with tabs[2]:
    if A["logit"] is None:
        answer(f"No model: {S['defects']} defects in {S['records']} jobs (both outcomes are needed).")
    else:
        lr = A["logit"]
        feats = lr["features"]
        defaults = {}
        if top:
            defaults[top["factor"]] = top["level"]
            for c in top["confounded_with"]:
                defaults[c["factor"]] = c["level"]
        cols = st.columns(len(feats))
        job = {}
        for col, f in zip(cols, feats):
            opts = stats.levels(df, f)
            idx = opts.index(defaults[f]) if defaults.get(f) in opts else 0
            job[f] = col.selectbox(FACTOR_LABELS[f], opts, index=idx, key=f"job_{f}")
        res_c = model.check_job(df, lr, job, high_t, med_t)
        icon = {"High": "⛔", "Medium": "⚠️", "Low": "✅"}[res_c["band"]]
        if res_c["bayes"]:
            bb = res_c["bayes"]
            rate_txt = (f"Past jobs with tool status <b>{html.escape(str(job.get('Tool_Status')))}</b>: "
                        f"{int(bb['defects'])} of {int(bb['jobs'])} defective · rate {bb['post_mean']:.0%} "
                        f"(90% range {bb['ci_low']:.0%}–{bb['ci_high']:.0%})")
        else:
            rate_txt = f"Model risk {res_c['probability']:.0%}"
        st.markdown(
            f'<div class="card band-{res_c["band"]}"><p class="band-title">{icon} {res_c["band"]} risk</p>'
            f'{rate_txt}<br><b>Recommendation:</b> {html.escape(res_c["recommendation"])}</div>',
            unsafe_allow_html=True)

        if A["tree"]:
            st.markdown(f"**Rule learned from {S['records']} jobs:**")
            st.markdown("- " + " · ".join(A["tree"]["english"]))

        v = A["validation"]["logistic"]
        if v["loo"]:
            lo = v["loo"]
            st.markdown(f"**Leave-one-out check:** recall {lo['recall']:.0%} ({lo['tp']} of {lo['tp'] + lo['fn']} "
                        f"defects caught), precision {lo['precision']:.0%} ({lo['fp']} false alarms).")
        if v["warnings"]:
            st.warning(" ".join(v["warnings"]))

        lk = A["leakage"]
        if lk and lk["validation"]["loo"]:
            sym = lk["validation"]["loo"]
            names = ", ".join(FACTOR_LABELS[f].replace("Belt ", "").lower() for f in lk["features"])
            st.markdown(f"**Leakage check:** a model using {names} also scores recall {sym['recall']:.0%} "
                        f"(AUC {sym['auc']:.2f}), but those are recorded with the defect, so they can't predict it.")


# ----------------------------------------------------------------------------- 4. Act

with tabs[3]:
    g = A["gate"]
    if g["defects_total"]:
        answer(f"Calibration gate: {g['defects_total']} defects occurred → {g['defects_remaining']} if only "
               f"calibrated tools had been used → {g['reduction_pct']:.0f}% fewer defects.")
    else:
        answer("Calibration gate: no defects recorded, so there is nothing for a gate to prevent.")
    aff = A["affected"]
    if aff.empty:
        st.markdown(f"No aircraft need follow-up among the {S['aircraft']} in this data.")
    else:
        short = {"Belt_Condition": "Condition", "Belt_Temperature": "Temperature", "Belt_Vibration": "Vibration"}
        readings = df[["Record_ID"] + SYM_PRESENT].rename(columns=short)
        view = aff.merge(readings, on="Record_ID", how="left")
        view = view[["Priority", "Record_ID", "Aircraft_ID", "Month", "Station", "Tool", "Tool status"]
                    + [short[c] for c in SYM_PRESENT] + ["Action"]]
        n_high = int(view["Priority"].str.startswith("1").sum())
        cap, dl = st.columns([4, 1])
        cap.caption(f"{view['Aircraft_ID'].nunique()} of {S['aircraft']} aircraft need inspection "
                    f"({n_high} high priority).")
        dl.download_button("Download CSV", view.to_csv(index=False).encode(), "aircraft_inspection_list.csv",
                           "text/csv", icon=":material/download:", width="stretch")
        tint = {"1": _rgba(ch.RED, .12), "2": _rgba(ch.AMBER, .14), "3": _rgba(ch.GREEN, .10)}
        styled = view.style.apply(lambda r: [f"background-color:{tint.get(str(r['Priority'])[0], '')}"] * len(r),
                                  axis=1)
        st.dataframe(styled, width="stretch", hide_index=True, height=min(35 * (len(view) + 1) + 3, 390))
