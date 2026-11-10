"""Business impact: calibration gate, affected-aircraft action list, per-aircraft fleet status."""
from __future__ import annotations

import pandas as pd

from .data import NORMAL_STATUS, SYMPTOMS
from .stats import suspect_mask


def calibration_gate(df: pd.DataFrame) -> dict:
    """If the work-order system blocked every tool not in Normal status, which defects remain?"""
    total = int(df["defect"].sum())
    blocked = df["Tool_Status"] != NORMAL_STATUS
    remaining = int(df.loc[~blocked, "defect"].sum())
    avoided = total - remaining
    return {"defects_total": total, "defects_remaining": remaining, "defects_avoided": avoided,
            "reduction_pct": (avoided / total * 100) if total else 0.0,
            "jobs_blocked": int(blocked.sum()), "jobs_total": len(df)}


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


ABNORMAL_VALUES = ("Abnormal", "High")
STATUS_ORDER = ["High Risk", "Medium", "Normal"]


def fleet_status(df: pd.DataFrame, top: dict | None) -> pd.DataFrame:
    """One row per aircraft with a belt status computed from the recorded data.

    High Risk: a defect was recorded, or two or more belt readings are abnormal.
    Medium:    one abnormal reading, or the job used the suspect factor or a tool not in Normal status.
    Normal:    everything else.
    If an aircraft appears more than once, its worst record is kept.
    """
    sus = suspect_mask(df, top)
    sym_cols = [c for c in SYMPTOMS if c in df.columns]
    abnormal = df[sym_cols].isin(ABNORMAL_VALUES).sum(axis=1) if sym_cols else pd.Series(0, index=df.index)
    tool_off = df["Tool_Status"] != NORMAL_STATUS
    status = pd.Series("Normal", index=df.index)
    status[(abnormal == 1) | sus | tool_off] = "Medium"
    status[(df["defect"] == 1) | (abnormal >= 2)] = "High Risk"

    out = pd.DataFrame({
        "Aircraft_ID": df["Aircraft_ID"], "Status": status, "Abnormal_readings": abnormal,
        "Defect": df["Belt_Defect"], "Suspect": sus, "Tool_ID": df["Tool_ID"], "Tool_Status": df["Tool_Status"],
        "Station": df["Maintenance_Station"], "Month": df["Month"], "Record_ID": df["Record_ID"],
    })
    for c in sym_cols:
        out[c] = df[c]
    out["_rank"] = out["Status"].map(STATUS_ORDER.index)
    out = (out.sort_values(["_rank", "Abnormal_readings", "Record_ID"], ascending=[True, False, True])
              .drop_duplicates("Aircraft_ID").drop(columns="_rank").reset_index(drop=True))
    return out
