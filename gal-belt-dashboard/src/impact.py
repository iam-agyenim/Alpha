"""Business impact: calibration gate, cost estimate, affected-aircraft action list."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .data import NORMAL_STATUS, SYMPTOMS
from .stats import suspect_mask


@dataclass
class CostAssumptions:
    cost_per_aog_hour: float = 10_000.0      # USD, placeholder
    aog_hours_per_failure: float = 24.0      # hours on ground per in-service belt failure
    share_to_in_service: float = 0.30        # share of missed defects that would fail in service
    cost_per_reinspection: float = 1_500.0   # USD per aircraft re-inspection


def calibration_gate(df: pd.DataFrame) -> dict:
    """If the work-order system blocked every tool not in Normal status, which defects remain?"""
    total = int(df["defect"].sum())
    blocked = df["Tool_Status"] != NORMAL_STATUS
    remaining = int(df.loc[~blocked, "defect"].sum())
    avoided = total - remaining
    return {"defects_total": total, "defects_remaining": remaining, "defects_avoided": avoided,
            "reduction_pct": (avoided / total * 100) if total else 0.0,
            "jobs_blocked": int(blocked.sum()), "jobs_total": len(df)}


def cost_estimate(defects_avoided: int, aircraft_to_reinspect: int, a: CostAssumptions) -> dict:
    failures = defects_avoided * a.share_to_in_service
    aog_cost = failures * a.aog_hours_per_failure * a.cost_per_aog_hour
    reinspect = aircraft_to_reinspect * a.cost_per_reinspection
    return {"in_service_failures_avoided": failures, "aog_hours_avoided": failures * a.aog_hours_per_failure,
            "aog_cost_avoided": aog_cost, "reinspection_cost": reinspect, "net_benefit": aog_cost - reinspect}


def affected_aircraft(df: pd.DataFrame, top: dict | None) -> pd.DataFrame:
    """Aircraft that need follow-up, with priority and recommended action."""
    sus = suspect_mask(df, top)
    sym_cols = [c for c in SYMPTOMS if c in df.columns]
    symptomatic = df[sym_cols].isin(["Abnormal", "High"]).any(axis=1) if sym_cols else pd.Series(False, index=df.index)
    rows = []
    for i, r in df.iterrows():
        if r["defect"] == 1:
            pri, action = "1 - High", "Replace/rework belt, set tension with a calibrated tool, re-inspect after rework"
        elif sus[i]:
            pri, action = "2 - Medium", "Serviced with suspect tool: check belt tension with a calibrated tool"
        elif symptomatic[i]:
            pri, action = "2 - Medium", "Abnormal reading without recorded defect: re-inspect belt"
        elif r["Tool_Status"] != NORMAL_STATUS:
            pri, action = "3 - Low", "Tool not in Normal status: verify tension at next check"
        else:
            continue
        rows.append({"Priority": pri, "Record_ID": r["Record_ID"], "Aircraft_ID": r["Aircraft_ID"],
                     "Month": r["Month"], "Station": r["Maintenance_Station"], "Tool": r["Tool_ID"],
                     "Tool status": r["Tool_Status"], "Defect": r["Belt_Defect"], "Action": action})
    cols = ["Priority", "Record_ID", "Aircraft_ID", "Month", "Station", "Tool", "Tool status", "Defect", "Action"]
    return pd.DataFrame(rows, columns=cols).sort_values(["Priority", "Record_ID"]).reset_index(drop=True)


def recommended_actions(top: dict | None) -> list[dict]:
    if top is None:
        return [{"action": "Keep monitoring", "why": "No pre-job factor stands out in this data.", "owner": "Reliability"}]
    tool_levels = [top["level"]] if top["factor"] == "Tool_ID" else \
        [c["level"] for c in top["confounded_with"] if c["factor"] == "Tool_ID"]
    tool = tool_levels[0] if tool_levels else None
    acts = []
    if tool:
        acts += [
            {"action": f"Quarantine {tool} and recalibrate it", "why": f"Linked to {top['defects']} of {top['jobs']} defective jobs.", "owner": "Tool store"},
            {"action": f"Test {tool} against a reference tool", "why": "Separates a faulty unit from a calibration lapse (they are confounded in the data).", "owner": "Quality"},
            {"action": f"Trace other aircraft serviced with {tool}", "why": "Exposure outside this dataset is unknown.", "owner": "Planning"},
        ]
    elif top["factor"] == "Tool_Status":
        acts.append({"action": f"Pull all tools with status '{top['level']}' from service", "why": "Linked to defects.", "owner": "Tool store"})
    else:
        acts.append({"action": f"Audit {top['label'].lower()} '{top['level']}'", "why": "Highest defect rate among pre-job factors.", "owner": "Quality"})
    acts += [
        {"action": "Re-inspect affected aircraft after rework", "why": "Confirm the belt is within limits once tension is reset.", "owner": "Line maintenance"},
        {"action": "Add a calibration gate to the work-order system", "why": "Block job sign-off when the selected tool is out of calibration.", "owner": "MRO IT / Quality"},
    ]
    return acts
