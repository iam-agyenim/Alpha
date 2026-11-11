"""Read-only tools the agents can call.

Every tool reads the trained model's saved predictions and the training data through fleet_analysis,
returns a small JSON-ready summary (never raw rows in bulk), and passes through guard.sanitize.
No tool can write, delete, run code or reach the internet.
Percentages are returned as percent numbers (6.6 means 6.6%).
"""
import re

import numpy as np
import pandas as pd

from .. import config
from .. import fleet_analysis as fa
from .guard import sanitize

AIRCRAFT_RE = re.compile(r"^B787-\d{3}$")
TOOL_RE = re.compile(r"^Tool-\d{2}$")
FACTORS = ["tension_band", "calibration_band", "tool", "station", "supplier"]
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


def tool_status(data: fa.FleetData) -> dict:
    t = fa.tool_summary(data)
    return {"overdue_rule": f"calibration load (days x uses / 1000) above {fa.OVERDUE_CALIBRATION_LOAD}",
            "latest_month": f"{data.test.month.max():%Y-%m}",
            "tools": [{
                "tool": r.Tool_ID, "training_defect_rate_pct": _pct(r.training_defect_rate),
                "test_predicted_defect_rate_pct": _pct(r.predicted_defect_rate),
                "latest_month_predicted_defect_rate_pct": _pct(r.latest_predicted_rate),
                "days_since_calibration": _num(r.days_since_calibration, 0),
                "uses_since_calibration": _num(r.uses_since_calibration, 0),
                "latest_avg_tension_difference_pct": _num(r.latest_tension_error),
                "test_overdue_share_pct": _pct(r.current_overdue_share, 0),
                "test_screenings": int(r.screenings),
            } for r in t.itertuples()]}


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


def measurement_signals(data: fa.FleetData) -> dict:
    lift = fa.abnormal_measurement_lift(data.train)
    limits = {fa.MEASUREMENTS[c][0]: _num(v) for c, v in data.normal_limits.items()}
    test = data.test
    abnormal_counts = {fa.MEASUREMENTS[c][0]: int(test[f"abnormal_{c}"].sum()) for c in fa.MEASUREMENTS}
    # Peer check: measurement says risky, model says low risk
    disagree = test[test.abnormal_any & (test.defect_probability < fa.MEDIUM_RISK_PROBABILITY)]
    examples = [{
        "record": r[config.ID_COLUMN], "aircraft": r.Aircraft_ID, "date": f"{r[config.DATE_COLUMN]:%Y-%m-%d}",
        "defect_risk_pct": _pct(r.defect_probability), "reasons": fa.screening_reasons(r, data.normal_limits)[:160],
    } for _, r in disagree.sort_values(config.DATE_COLUMN).tail(8).iterrows()]
    return {
        "normal_range_upper_limits": limits,
        "normal_range_rule": "99% of defect-free training screenings were inside these limits",
        "training_lift": [{"measurement": r.measurement, "defect_rate_if_abnormal_pct": _pct(r.rate_abnormal),
                           "defect_rate_if_normal_pct": _pct(r.rate_normal),
                           "times_more_likely": _num(r.times_more_likely)} for r in lift.itertuples()],
        "test_abnormal_screenings": abnormal_counts,
        "abnormal_but_model_low_risk": {"count": int(len(disagree)), "latest_examples": examples},
    }


def defect_rate_by_factor(data: fa.FleetData, factor: str) -> dict:
    train = data.train
    if factor == "tension_band":
        t, col = fa.defect_rate_by_tension_band(train), "tension_band"
    elif factor == "calibration_band":
        t, col = fa.defect_rate_by_calibration(train), "calibration_band"
    elif factor in ("tool", "station", "supplier"):
        col = {"tool": "Tool_ID", "station": "Maintenance_Station", "supplier": "Belt_Supplier"}[factor]
        t = fa.defect_rate_by(train, col)
    else:
        return {"error": f"factor must be one of {FACTORS}"}
    return {"factor": factor, "source": "training data, actual outcomes",
            "groups": [{"group": str(r[col]), "defect_rate_pct": _pct(r.defect_rate),
                        "screenings": int(r.screenings)} for _, r in t.iterrows()]}


def monthly_trend(data: fa.FleetData) -> dict:
    t = fa.monthly_defect_trend(data)
    return {"note": "Actual = confirmed outcomes; Predicted = model predictions for the test period",
            "months": [{"month": f"{r.month:%Y-%m}", "source": r.source, "defect_rate_pct": _pct(r.defect_rate),
                        "screenings": int(r.screenings), "avg_ambient_temp_c": _num(r.ambient_temp),
                        "overdue_tool_share_pct": _pct(r.overdue_share, 0),
                        "avg_abs_tension_difference_pct": _num(r.tension_error)} for r in t.itertuples()]}


def seasonal_comparison(data: fa.FleetData) -> dict:
    """Same calendar months a year apart (actual for training months, predicted for test months)."""
    t = fa.monthly_defect_trend(data)
    t = t.assign(year=t.month.dt.year, cal_month=t.month.dt.month)
    t = t.sort_values("source").drop_duplicates(["year", "cal_month"])   # prefer Actual where both exist
    pivot = t.pivot(index="cal_month", columns="year", values="defect_rate")
    rows = []
    for m, r in pivot.iterrows():
        vals = {str(y): _pct(v) for y, v in r.items() if not pd.isna(v)}
        if len(vals) >= 2:
            rows.append({"calendar_month": int(m), **{f"defect_rate_{y}_pct": v for y, v in vals.items()}})
    tr = data.train
    spring_rows = tr[tr.month.dt.month.isin([4, 5])]
    spring = spring_rows.groupby(spring_rows.month.dt.year)[config.LABEL_COLUMN].mean()   # actual, all screenings
    return {"same_month_comparison": rows,
            "apr_may_defect_rate_pct_by_year": {str(y): _pct(v) for y, v in spring.items()}}


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
def _schema(props: dict | None = None) -> dict:
    props = props or {}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


TOOLS = {
    "fleet_overview": (fleet_overview, "Fleet headline numbers: aircraft per status, test period, predicted "
                       "defects, base rates, Yes threshold and the tool most linked to current risk.", _schema()),
    "list_aircraft": (list_aircraft, "Aircraft ranked by belt status and defect risk (latest screening), with "
                      "reasons.", _schema({"status": {"type": "string", "enum": STATUSES},
                                           "limit": {"type": "integer", "description": "1-25"}})),
    "aircraft_history": (aircraft_history, "All test-period screenings of one aircraft (risk over time, tool, "
                         "measurements).", _schema({"aircraft_id": {"type": "string",
                                                                    "description": "e.g. B787-022"}})),
    "tool_status": (tool_status, "Every tension tool: calibration age, uses, tension error, historical and "
                    "predicted defect rates.", _schema()),
    "tool_history": (tool_history, "One tool month by month: days since calibration, tension error, defect "
                     "rate.", _schema({"tool_id": {"type": "string", "description": "e.g. Tool-03"}})),
    "measurement_signals": (measurement_signals, "Normal ranges, how much each abnormal measurement raises "
                            "defect odds, abnormal counts in the test period, and screenings where measurements "
                            "look abnormal but the model says low risk.", _schema()),
    "defect_rate_by_factor": (defect_rate_by_factor, "Actual training defect rate by a factor.",
                              _schema({"factor": {"type": "string", "enum": FACTORS}})),
    "monthly_trend": (monthly_trend, "Monthly defect rate (actual then predicted), temperature and overdue-tool "
                      "share.", _schema()),
    "seasonal_comparison": (seasonal_comparison, "Defect rate in the same months a year apart.", _schema()),
    "model_card": (model_card, "How good the prediction model is, how it was tested, and its limits.", _schema()),
}


def openai_tool_specs(names: list) -> list:
    return [{"type": "function", "name": n, "description": TOOLS[n][1], "parameters": TOOLS[n][2], "strict": True}
            for n in names]


def call_tool(data: fa.FleetData, name: str, args: dict, allowed: list) -> dict:
    """Run one tool. Refuses tools outside the agent's allowlist; output is always sanitised."""
    if name not in allowed or name not in TOOLS:
        return {"error": f"tool '{name}' is not available to this agent"}
    try:
        result = TOOLS[name][0](data, **(args or {}))
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
