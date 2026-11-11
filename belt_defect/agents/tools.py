"""Read-only tools the agents can call.

Every tool reads the trained model's saved predictions and the training data (and, for business tools, the
user's cost assumptions),
returns a small JSON-ready summary (never raw rows in bulk), and passes through guard.sanitize.
No tool can write, delete, run code or reach the internet.
Percentages are returned as percent numbers (6.6 means 6.6%).
"""
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import config
from .. import fleet_analysis as fa
from . import business as B
from .guard import sanitize

AIRCRAFT_RE = re.compile(r"^B787-\d{3}$")
TOOL_RE = re.compile(r"^Tool-\d{2}$")
STATUSES = [fa.STATUS_HIGH, fa.STATUS_MEDIUM, fa.STATUS_NORMAL, "any"]


def _pct(x, digits=1):
    return None if x is None or pd.isna(x) else round(float(x) * 100, digits)


def _num(x, digits=1):
    return None if x is None or pd.isna(x) else round(float(x), digits)


# --------------------------------------------------------------------------- tool functions
def fleet_overview(data: fa.FleetData) -> dict:
    aircraft = fa.aircraft_status(data)
    tools = fa.tool_summary(data)
    alert = fa.fleet_alert(aircraft, tools)
    counts = aircraft["Belt Status"].value_counts()
    return {
        "aircraft_total": int(len(aircraft)),
        "aircraft_by_status_latest_screening": {s: int(counts.get(s, 0)) for s in fa.STATUS_ORDER},
        "test_period": f"{data.test[config.DATE_COLUMN].min():%Y-%m-%d} to {data.test[config.DATE_COLUMN].max():%Y-%m-%d}",
        "test_screenings": int(len(data.test)),
        "test_predicted_defects": int(data.test.predicted_defect.sum()),
        "test_predicted_defect_rate_pct": _pct(data.test.predicted_defect.mean()),
        "training_screenings": int(len(data.train)),
        "training_defect_rate_pct": _pct(data.train[config.LABEL_COLUMN].mean()),
        "yes_threshold_pct": _pct(data.threshold),
        "medium_rule": "defect risk >= 20% or any measurement outside the normal range",
        "problem_tool": alert["tool_id"],
    }


def list_aircraft(data: fa.FleetData, status: str, limit: int) -> dict:
    if status not in STATUSES:
        return {"error": f"status must be one of {STATUSES}"}
    limit = int(min(max(limit, 1), 25))
    table = fa.aircraft_status(data)
    if status != "any":
        table = table[table["Belt Status"] == status]
    rows = [{
        "aircraft": r.Aircraft, "status": r._2, "defect_risk_pct": _pct(r._7),
        "tension_difference_pct": _num(r._3), "tool": r.Tool, "engine": r.Engine,
        "screening_date": str(r._6), "reasons": r.Why[:160],
    } for r in table.head(limit).itertuples()]
    return {"status_filter": status, "matching_aircraft": int(len(table)), "shown": len(rows), "aircraft": rows}


def aircraft_history(data: fa.FleetData, aircraft_id: str) -> dict:
    if not AIRCRAFT_RE.match(aircraft_id or ""):
        return {"error": "aircraft_id must look like B787-022"}
    rows = data.test[data.test.Aircraft_ID == aircraft_id].sort_values(config.DATE_COLUMN)
    if rows.empty:
        return {"error": f"no test-period screenings for {aircraft_id}"}
    out = []
    for _, r in rows.tail(30).iterrows():
        out.append({
            "date": f"{r[config.DATE_COLUMN]:%Y-%m-%d}", "engine": r.Engine_ID, "tool": r.Tool_ID,
            "defect_risk_pct": _pct(r.defect_probability), "status": fa.belt_status(r),
            "tension_difference_pct": _num(r.Tension_Dev_Pct), "belt_temperature_c": _num(r.Belt_Temperature_C),
            "vibration_mm_s": _num(r.Belt_Vibration_mm_s),
            "tool_days_since_calibration": _num(r.Days_Since_Tool_Calibration, 0),
            "tool_overdue": bool(r.calibration_overdue),
        })
    return {"aircraft": aircraft_id, "screenings_in_test_period": int(len(rows)),
            "predicted_defects": int(rows.predicted_defect.sum()), "latest_screenings": out}


def tool_history(data: fa.FleetData, tool_id: str) -> dict:
    if not TOOL_RE.match(tool_id or ""):
        return {"error": "tool_id must look like Tool-03"}
    drift = fa.tool_monthly_drift(data, tool_id)
    if drift.empty:
        return {"error": f"unknown tool {tool_id}"}
    return {"tool": tool_id, "months": [{
        "month": f"{r.month:%Y-%m}", "source": r.source,
        "avg_days_since_calibration": _num(r.days_since_calibration, 0),
        "avg_tension_difference_pct": _num(r.tension_error), "defect_rate_pct": _pct(r.defect_rate),
    } for r in drift.itertuples()]}


def monthly_trend(data: fa.FleetData) -> dict:
    t = fa.monthly_defect_trend(data)
    return {"note": "Actual = confirmed outcomes; Predicted = model predictions for the test period",
            "months": [{"month": f"{r.month:%Y-%m}", "source": r.source, "defect_rate_pct": _pct(r.defect_rate),
                        "screenings": int(r.screenings), "avg_ambient_temp_c": _num(r.ambient_temp),
                        "overdue_tool_share_pct": _pct(r.overdue_share, 0),
                        "avg_abs_tension_difference_pct": _num(r.tension_error)} for r in t.itertuples()]}


def model_card(data: fa.FleetData) -> dict:
    m = data.oof_metrics
    return {"model": "average of LightGBM, CatBoost and logistic regression probabilities",
            "cross_validated": {"f1": _num(m["F1"], 3), "precision": _num(m["Precision"], 3),
                                "recall": _num(m["Recall"], 3), "scheme": "5-fold x 3 repeats on 10000 rows"},
            "time_based_check": {"f1": 0.702, "precision": 0.687, "recall": 0.719,
                                 "scheme": "train on first 8000 by date, predict last 2000"},
            "yes_threshold_pct": _pct(data.threshold),
            "excluded_inputs": ["Technician_ID", "month"],
            "limits": ["synthetic data", "associations are not proof of cause",
                       "decision support only, not a certified maintenance system"]}


# --------------------------------------------------------------------------- registry
@dataclass
class ToolContext:
    """What a tool can see: the fleet data (model predictions + training data) and the business assumptions."""
    data: fa.FleetData
    assumptions: B.Assumptions


def _schema(props: dict | None = None) -> dict:
    props = props or {}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def _d(fn):            # tool that needs only the data
    return lambda ctx, **kw: fn(ctx.data, **kw)


def _da(fn):           # tool that needs data + business assumptions
    return lambda ctx, **kw: fn(ctx.data, ctx.assumptions, **kw)


TOOLS = {
    # --- evidence: what the model and data say ---
    "problem_register": (_d(B.problem_register), "The measured business problems behind belt defects, each with "
                         "its share of defects (calibration lapses, wrong tension, heat, no early warning).", _schema()),
    "tension_calibration_matrix": (_d(B.tension_calibration_matrix), "Defect rate and share of defects for overdue "
                                   "vs calibrated tools crossed with tension more/less than 6% off target.", _schema()),
    "supplier_tool_interaction": (_d(B.supplier_tool_interaction), "Defect rate per belt supplier with and without "
                                  "an overdue tool (is the supplier the problem, or the tool?).", _schema()),
    "tools_at_risk_now": (_d(B.tools_at_risk_now), "Every tool's calibration load now, tension error and the model's "
                          "predicted defect rate for its latest jobs.", _schema()),
    "tool_history": (_d(tool_history), "One tool month by month: days since calibration, tension error, defect rate.",
                     _schema({"tool_id": {"type": "string", "description": "e.g. Tool-03"}})),
    "fleet_overview": (_d(fleet_overview), "Fleet headline: aircraft per risk status now, predicted defects, base "
                       "rates, threshold.", _schema()),
    "list_aircraft": (_d(list_aircraft), "Aircraft ranked by belt status and model risk, with reasons.",
                      _schema({"status": {"type": "string", "enum": STATUSES},
                               "limit": {"type": "integer", "description": "1-25"}})),
    "aircraft_history": (_d(aircraft_history), "All recent screenings of one aircraft (risk over time, tool, "
                         "measurements).", _schema({"aircraft_id": {"type": "string", "description": "e.g. B787-022"}})),
    "monthly_trend": (_d(monthly_trend), "Monthly defect rate (actual then predicted), temperature and overdue-tool "
                      "share.", _schema()),
    "model_card": (_d(model_card), "How accurate the ML model is, how it was tested, and its limits.", _schema()),
    # --- business calculators (use the assumptions: fleet size, unit costs, policy settings) ---
    "calibration_policy_options": (_da(B.calibration_policy_options), "For calibration-load triggers 30/45/60/90: "
                                   "defects avoided, extra calibrations, value, cost and net value per year for the "
                                   "planned fleet.", _schema()),
    "tension_check_policy": (_da(B.tension_check_policy), "For re-tension triggers (4/6/8% off target): share of "
                             "defects covered, re-tensions and cost per year.", _schema()),
    "inspection_capture_curve": (_da(B.inspection_capture_curve), "Inspect the model's top X% riskiest screenings: "
                                 "defects caught, inspections, yield and cost per year, vs blanket inspection.",
                                 _schema()),
    "season_plan": (_da(B.season_plan), "Hot-season effect, year-on-year spring change and predicted monthly belt "
                    "replacements for the planned fleet.", _schema()),
    "enterprise_cost": (_da(B.enterprise_cost), "Cost of running this AI system at the planned scale: AI tokens and "
                        "total cost of ownership.", _schema()),
    "business_value": (_da(B.business_value), "Value, costs, net benefit, return and payback for a policy choice. "
                       "Pass the calibration trigger, re-tension trigger and inspection share you want to price.",
                       _schema({"calibration_limit": {"type": "number", "enum": B.CALIBRATION_LIMITS},
                                "tension_limit_pct": {"type": "number", "enum": B.TENSION_LIMITS},
                                "inspection_top_pct": {"type": "number", "enum": B.INSPECTION_TOP_PCTS}})),
}


def openai_tool_specs(names: list) -> list:
    return [{"type": "function", "name": n, "description": TOOLS[n][1], "parameters": TOOLS[n][2], "strict": True}
            for n in names]


def call_tool(ctx: ToolContext, name: str, args: dict, allowed: list) -> dict:
    """Run one tool. Refuses tools outside the agent's allowlist; output is always sanitised."""
    if name not in allowed or name not in TOOLS:
        return {"error": f"tool '{name}' is not available to this agent"}
    try:
        result = TOOLS[name][0](ctx, **(args or {}))
    except TypeError as err:
        result = {"error": f"bad arguments: {err}"}
    except Exception as err:                          # never crash the team on one tool
        result = {"error": f"tool failed: {type(err).__name__}"}
    return sanitize(_jsonable(result))


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj
