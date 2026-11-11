"""Read-only tools the workflow agents can call.

Facts come from the trained model's saved predictions and the maintenance data. Logistics and commercial facts
the dataset doesn't hold (belt stock, calibration slots, flight schedule, unit costs) come from OPS_ASSUMPTIONS
and are always labelled as assumptions. Every tool returns a small JSON summary and passes through
guard.sanitize; no tool can write, delete, run code or reach the internet. Percentages are percent numbers.
"""
import re
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from .. import config
from .. import fleet_analysis as fa
from .guard import sanitize

AIRCRAFT_RE = re.compile(r"^B787-\d{3}$")
TOOL_RE = re.compile(r"^Tool-\d{2}$")
STATUSES = [fa.STATUS_HIGH, fa.STATUS_MEDIUM, fa.STATUS_NORMAL, "any"]

OPS_ASSUMPTIONS = {
    "belt_stock_by_station": {"Station A": 4, "Station B": 3, "Station C": 2},
    "belt_order_lead_time_days": 2,
    "calibration_lab_slots": ["Today 14:00", "Today 16:00", "Tomorrow 09:00", "Tomorrow 11:00"],
    "technicians_per_shift_by_station": {"Station A": 3, "Station B": 2, "Station C": 2},
    "inspection_hours_per_aircraft": 1.5,
    "shift_hours": 8,
    "average_sector_hours": 4.5,
    "cost_per_defect_usd": 5000,
    "inspection_cost_usd": 300,
    "calibration_cost_usd": 150,
    "aog_event_cost_usd": 100000,
}


@dataclass
class ToolContext:
    """What tools can see: fleet data (model predictions + training data), the batch being processed, assumptions."""
    data: fa.FleetData
    batch: pd.DataFrame
    ops: dict = field(default_factory=lambda: dict(OPS_ASSUMPTIONS))

    @property
    def batch_data(self) -> fa.FleetData:
        return replace(self.data, test=self.batch)


def _pct(x, digits=1):
    return None if x is None or pd.isna(x) else round(float(x) * 100, digits)


def _num(x, digits=1):
    return None if x is None or pd.isna(x) else round(float(x), digits)


def _latest_by_aircraft(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(config.DATE_COLUMN).groupby("Aircraft_ID").tail(1).set_index("Aircraft_ID")


# --------------------------------------------------------------------------- quality and safety
def batch_risk_summary(ctx: ToolContext) -> dict:
    b = ctx.batch_data
    aircraft = fa.aircraft_status(b)
    tools = fa.tool_summary(b)
    counts = aircraft["Belt Status"].value_counts()
    return {
        "batch_period": f"{ctx.batch[config.DATE_COLUMN].min():%Y-%m-%d} to {ctx.batch[config.DATE_COLUMN].max():%Y-%m-%d}",
        "screenings": int(len(ctx.batch)), "aircraft": int(ctx.batch.Aircraft_ID.nunique()),
        "predicted_defects": int(ctx.batch.predicted_defect.sum()),
        "predicted_defect_rate_pct": _pct(ctx.batch.predicted_defect.mean()),
        "aircraft_by_status": {s: int(counts.get(s, 0)) for s in fa.STATUS_ORDER},
        "yes_threshold_pct": _pct(ctx.data.threshold),
        "tool_most_linked_to_risk": tools.iloc[0].Tool_ID,
        "model": "average of LightGBM, CatBoost and logistic regression; cross-validated F1 0.751",
    }


def list_aircraft(ctx: ToolContext, status: str, limit: int) -> dict:
    if status not in STATUSES:
        return {"error": f"status must be one of {STATUSES}"}
    table = fa.aircraft_status(ctx.batch_data)
    if status != "any":
        table = table[table["Belt Status"] == status]
    rows = [{"aircraft": r.Aircraft, "status": r._2, "defect_risk_pct": _pct(r._7),
             "tension_difference_pct": _num(r._3), "tool": r.Tool, "engine": r.Engine,
             "screening_date": str(r._6), "reasons": r.Why[:150]}
            for r in table.head(int(min(max(limit, 1), 25))).itertuples()]
    return {"status_filter": status, "matching_aircraft": int(len(table)), "aircraft": rows}


def aircraft_history(ctx: ToolContext, aircraft_id: str) -> dict:
    if not AIRCRAFT_RE.match(aircraft_id or ""):
        return {"error": "aircraft_id must look like B787-022"}
    rows = ctx.data.test[ctx.data.test.Aircraft_ID == aircraft_id].sort_values(config.DATE_COLUMN)
    if rows.empty:
        return {"error": f"no recent screenings for {aircraft_id}"}
    return {"aircraft": aircraft_id, "screenings": int(len(rows)), "predicted_defects": int(rows.predicted_defect.sum()),
            "latest": [{"date": f"{r[config.DATE_COLUMN]:%Y-%m-%d}", "engine": r.Engine_ID, "tool": r.Tool_ID,
                        "station": r.Maintenance_Station, "defect_risk_pct": _pct(r.defect_probability),
                        "status": fa.belt_status(r), "tension_difference_pct": _num(r.Tension_Dev_Pct),
                        "belt_temperature_c": _num(r.Belt_Temperature_C), "vibration_mm_s": _num(r.Belt_Vibration_mm_s)}
                       for _, r in rows.tail(8).iterrows()]}


def tools_at_risk(ctx: ToolContext) -> dict:
    t = fa.tool_summary(ctx.batch_data)
    return {"overdue_rule": f"calibration load (days x uses / 1000) above {fa.OVERDUE_CALIBRATION_LOAD}",
            "tools": [{"tool": r.Tool_ID, "days_since_calibration": _num(r.days_since_calibration, 0),
                       "uses_since_calibration": _num(r.uses_since_calibration, 0),
                       "calibration_load": _num(r.days_since_calibration * r.uses_since_calibration / 1000, 0),
                       "avg_tension_difference_pct": _num(r.latest_tension_error),
                       "predicted_defect_rate_pct": _pct(r.latest_predicted_rate),
                       "training_defect_rate_pct": _pct(r.training_defect_rate)} for r in t.itertuples()]}


def measurement_signals(ctx: ToolContext) -> dict:
    lift = fa.abnormal_measurement_lift(ctx.data.train)
    b = ctx.batch
    disagree = b[b.abnormal_any & (b.defect_probability < fa.MEDIUM_RISK_PROBABILITY)]
    return {"normal_range_upper_limits": {fa.MEASUREMENTS[c][0]: _num(v) for c, v in ctx.data.normal_limits.items()},
            "times_more_likely_if_abnormal": {r.measurement: _num(r.times_more_likely) for r in lift.itertuples()},
            "abnormal_screenings_in_batch": {fa.MEASUREMENTS[c][0]: int(b[f"abnormal_{c}"].sum()) for c in fa.MEASUREMENTS},
            "abnormal_but_model_low_risk": int(len(disagree)),
            "abnormal_but_low_risk_aircraft": sorted(disagree.Aircraft_ID.unique().tolist())[:10]}


# --------------------------------------------------------------------------- logistics
def aircraft_locations(ctx: ToolContext, aircraft_ids: list) -> dict:
    ids = [a for a in (aircraft_ids or []) if AIRCRAFT_RE.match(str(a))][:25]
    latest = _latest_by_aircraft(ctx.data.test)
    return {"source": "station of each aircraft's latest screening",
            "aircraft": [{"aircraft": a, "station": latest.loc[a, "Maintenance_Station"],
                          "engine": latest.loc[a, "Engine_ID"], "last_screening": f"{latest.loc[a, config.DATE_COLUMN]:%Y-%m-%d}"}
                         for a in ids if a in latest.index]}


def logistics_context(ctx: ToolContext) -> dict:
    t = fa.tool_summary(ctx.batch_data)
    load = t.days_since_calibration * t.uses_since_calibration / 1000
    o = ctx.ops
    return {"ASSUMPTION": "stock, slots and staffing are planning assumptions, not data",
            "belt_stock_by_station": o["belt_stock_by_station"],
            "belt_order_lead_time_days": o["belt_order_lead_time_days"],
            "calibration_lab_slots": o["calibration_lab_slots"],
            "technicians_per_shift_by_station": o["technicians_per_shift_by_station"],
            "inspection_hours_per_aircraft": o["inspection_hours_per_aircraft"], "shift_hours": o["shift_hours"],
            "loan_tools_in_calibration": sorted(t.loc[load < 60, "Tool_ID"].tolist())}


def plan_parts_and_staff(ctx: ToolContext, aircraft_ids: list) -> dict:
    """Calculator: belts needed per station vs stock, and technician hours vs one shift, for the given aircraft."""
    ids = [a for a in (aircraft_ids or []) if AIRCRAFT_RE.match(str(a))][:40]
    latest = _latest_by_aircraft(ctx.data.test)
    stations = pd.Series([latest.loc[a, "Maintenance_Station"] for a in ids if a in latest.index], dtype=object)
    o = ctx.ops
    out = []
    for station in sorted(set(stations) | set(o["belt_stock_by_station"])):
        needed = int((stations == station).sum())
        stock = int(o["belt_stock_by_station"].get(station, 0))
        hours = needed * o["inspection_hours_per_aircraft"]
        capacity = o["technicians_per_shift_by_station"].get(station, 0) * o["shift_hours"]
        out.append({"station": station, "belts_needed": needed, "belts_in_stock": stock,
                    "belts_to_order": max(needed - stock, 0), "technician_hours_needed": round(hours, 1),
                    "technician_hours_per_shift": capacity, "fits_in_one_shift": hours <= capacity})
    return {"ASSUMPTION": "one replacement belt reserved per inspected aircraft; stock and staffing are assumptions",
            "aircraft_counted": int(len(stations)), "stations": out,
            "total_belts_to_order": int(sum(s["belts_to_order"] for s in out))}


# --------------------------------------------------------------------------- commercial
def cost_of_plan(ctx: ToolContext, inspections: int, calibrations: int) -> dict:
    """Calculator: cost of the proposed actions vs predicted defect cost at risk in this batch."""
    o = ctx.ops
    inspections, calibrations = max(int(inspections), 0), max(int(calibrations), 0)
    action_cost = inspections * o["inspection_cost_usd"] + calibrations * o["calibration_cost_usd"]
    at_risk = int(ctx.batch.predicted_defect.sum()) * o["cost_per_defect_usd"]
    return {"ASSUMPTION": "unit costs are planning assumptions", "inspections": inspections,
            "calibrations": calibrations, "inspection_cost_usd": inspections * o["inspection_cost_usd"],
            "calibration_cost_usd": calibrations * o["calibration_cost_usd"], "action_cost_usd": action_cost,
            "predicted_defect_cost_at_risk_usd": at_risk, "one_aog_event_usd": o["aog_event_cost_usd"],
            "cost_to_risk_ratio_pct": round(action_cost / at_risk * 100, 1) if at_risk else None}


def flight_exposure(ctx: ToolContext, aircraft_ids: list) -> dict:
    ids = [a for a in (aircraft_ids or []) if AIRCRAFT_RE.match(str(a))][:25]
    latest = _latest_by_aircraft(ctx.data.test)
    sector = ctx.ops["average_sector_hours"]
    rows = []
    for a in ids:
        if a in latest.index:
            hours_per_day = float(latest.loc[a, "Operating_Hours_Last_30_Days"]) / 30
            rows.append({"aircraft": a, "flight_hours_per_day": round(hours_per_day, 1),
                         "estimated_flights_next_24h": int(round(hours_per_day / sector))})
    return {"ASSUMPTION": f"flights estimated from 30-day operating hours and a {sector}h average sector",
            "aircraft": rows, "total_estimated_flights_next_24h": int(sum(r["estimated_flights_next_24h"] for r in rows))}


def cost_context(ctx: ToolContext) -> dict:
    o = ctx.ops
    predicted = int(ctx.batch.predicted_defect.sum())
    return {"ASSUMPTION": "unit costs are planning assumptions; replace with company figures",
            "cost_per_defect_usd": o["cost_per_defect_usd"], "inspection_cost_usd": o["inspection_cost_usd"],
            "calibration_cost_usd": o["calibration_cost_usd"], "aog_event_cost_usd": o["aog_event_cost_usd"],
            "predicted_defects_in_batch": predicted,
            "predicted_defect_cost_at_risk_usd": predicted * o["cost_per_defect_usd"]}


# --------------------------------------------------------------------------- registry
def _schema(props: dict | None = None) -> dict:
    props = props or {}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


_IDS = {"aircraft_ids": {"type": "array", "items": {"type": "string"}, "description": "e.g. [\"B787-022\"]"}}

TOOLS = {
    "batch_risk_summary": (batch_risk_summary, "Model results for this batch: screenings, predicted defects, aircraft "
                           "per risk status, threshold, tool most linked to risk.", _schema()),
    "list_aircraft": (list_aircraft, "Aircraft in this batch ranked by belt status and model risk, with reasons.",
                      _schema({"status": {"type": "string", "enum": STATUSES},
                               "limit": {"type": "integer", "description": "1-25"}})),
    "aircraft_history": (aircraft_history, "Recent screenings of one aircraft (risk, tool, station, measurements).",
                         _schema({"aircraft_id": {"type": "string", "description": "e.g. B787-022"}})),
    "tools_at_risk": (tools_at_risk, "Every tension tool: calibration age, uses, load, tension error, predicted "
                      "defect rate.", _schema()),
    "measurement_signals": (measurement_signals, "Normal ranges, how much abnormal readings raise defect odds, "
                            "abnormal counts in the batch, and abnormal-but-low-risk screenings.", _schema()),
    "aircraft_locations": (aircraft_locations, "Station and engine for each aircraft (latest screening).",
                           _schema(_IDS)),
    "logistics_context": (logistics_context, "Belt stock per station, order lead time, calibration lab slots, "
                          "technicians per shift, loan tools (assumptions).", _schema()),
    "plan_parts_and_staff": (plan_parts_and_staff, "Calculator: belts needed vs stock per station and technician "
                             "hours vs one shift, for the aircraft to inspect.", _schema(_IDS)),
    "cost_of_plan": (cost_of_plan, "Calculator: cost of N inspections and M calibrations vs the predicted defect cost "
                     "at risk.", _schema({"inspections": {"type": "integer"}, "calibrations": {"type": "integer"}})),
    "flight_exposure": (flight_exposure, "Estimated flights in the next 24 hours for each aircraft (assumption).",
                        _schema(_IDS)),
    "cost_context": (cost_context, "Unit costs (assumptions) and predicted defect cost at risk for this batch.",
                     _schema()),
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
    except Exception as err:
        result = {"error": f"tool failed: {type(err).__name__}"}
    return sanitize(_jsonable(result))


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj
