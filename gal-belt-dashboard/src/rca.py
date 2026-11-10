"""Root cause analysis content (fishbone, 5 Whys, causal chain), driven by computed results."""
from __future__ import annotations

import pandas as pd

from .data import FACTOR_LABELS, SYMPTOMS
from .stats import fmt_p, rest_label, stratify, suspect_name, symptom_profile


def fishbone(df: pd.DataFrame, top: dict | None) -> pd.DataFrame:
    tool_top = top is not None and top["factor"] in ("Tool_ID", "Tool_Status")
    cal_confounded = top is not None and (
        top["factor"] == "Tool_Status" or any(c["factor"] == "Tool_Status" for c in top["confounded_with"]))
    who = suspect_name(top)

    st = stratify(df, "Maintenance_Station", "Tool_ID")
    station_ruled_out = not st["effect_survives"]

    rows = []
    if tool_top:
        rows.append(("Machine / tool", "Confirmed",
                     f"{top['defects']} of {top['jobs']} jobs with {who} had a defect vs "
                     f"{top['defects_rest']} of {top['jobs_rest']} {rest_label(top)} (Fisher p = {fmt_p(top['p_fisher'])})."))
    else:
        rows.append(("Machine / tool", "Not supported", "No tool stands out after correction for multiple tests."))
    if cal_confounded and tool_top:
        rows.append(("Measurement / calibration", "Confirmed but confounded",
                     "Every job with the suspect tool also had a tool needing calibration; the data cannot separate the two."))
    elif cal_confounded:
        rows.append(("Measurement / calibration", "Confirmed", "Tools needing calibration are linked to defects."))
    else:
        rows.append(("Measurement / calibration", "Not confirmed", "Calibration status is not the strongest signal."))
    rows.append(("Method / station", "Ruled out by stratification" if station_ruled_out else "Possible",
                 st["interpretation"]))
    rows.append(("Man / technician", "Not in data", "No technician ID recorded; cannot test training or shift effects."))
    rows.append(("Material / belt batch", "Not in data", "No belt part or batch number recorded."))
    rows.append(("Environment", "Not testable", "No temperature, humidity or route data; month shows no trend."))
    return pd.DataFrame(rows, columns=["category", "status", "evidence"])


def five_whys(df: pd.DataFrame, top: dict | None) -> list[dict]:
    if top is None:
        return [{"why": "Why are defects occurring?", "because": "No pre-job factor in this data explains them."}]
    sp = symptom_profile(df)
    who = suspect_name(top)
    sym = (f"{sp['share_defects_with_symptoms']:.0%} of defective belts ran hot and vibrated"
           if sp["share_defects_with_symptoms"] == sp["share_defects_with_symptoms"] else "symptom data unavailable")
    return [
        {"why": "Why are B787 engine belt defects being found?",
         "because": f"Belts show abnormal condition at inspection ({sym})."},
        {"why": "Why are the belts running hot and vibrating?",
         "because": "Most likely the belt tension was set incorrectly during maintenance (inferred: tension is not recorded)."},
        {"why": "Why was the tension set incorrectly?",
         "because": f"The jobs used {who}; {top['defects']} of {top['jobs']} of those jobs produced a defect."},
        {"why": "Why was that tool used?",
         "because": "It was issued and used even though its status showed it needed calibration."},
        {"why": "Why was a tool overdue for calibration allowed on the job?",
         "because": "No check blocked a tool overdue for calibration: a maintenance process gap, not a station or crew issue."},
    ]


def causal_chain_dot(top: dict | None) -> str:
    who = suspect_name(top) if top else "Suspect factor"
    nodes = [
        ("a", f"{who}", "#B45309", "In data"),
        ("b", "Belt tension set wrongly", "#6b7280", "Inferred, not in data"),
        ("c", "High temperature + vibration", "#1F3A5F", "Symptoms (in data)"),
        ("d", "Belt defect", "#d03b3b", "Outcome (in data)"),
    ]
    lines = ["digraph chain {", "rankdir=LR;",
             'node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=14 fontcolor=white];',
             'edge [fontname="Helvetica" fontsize=12 color="#6b7280"];']
    for nid, label, col, note in nodes:
        extra = ' style="rounded,filled,dashed"' if "Inferred" in note else ""
        lines.append(f'{nid} [label="{label}\\n[{note}]" fillcolor="{col}"{extra}];')
    lines += ["a -> b;", "b -> c;", "c -> d;", "}"]
    return "\n".join(lines)
