"""Business calculators the agents use: every dollar and every count they quote comes from here.

Rates and counts are measured on the 100-aircraft dataset (training data = actual outcomes over ~16 months;
OOF probabilities = the model's out-of-fold risk scores). They are annualised and scaled to the fleet size in
`Assumptions`. Unit costs are assumptions the user can edit in the dashboard.
"""
import math
from dataclasses import asdict, dataclass, replace

import numpy as np
import pandas as pd

from .. import config
from .. import fleet_analysis as fa

DATA_AIRCRAFT = 100
TOOLS_PER_100_AIRCRAFT = 8


@dataclass
class Assumptions:
    fleet_aircraft: int = 1000            # size of the business we plan for
    bases: int = 20
    users: int = 1500
    cost_per_defect_usd: float = 5000     # replacement + labour + downtime + share of in-service failures
    inspection_cost_usd: float = 300      # one detailed belt inspection
    calibration_cost_usd: float = 150     # one tool calibration
    retension_cost_usd: float = 100       # re-check and re-tension one belt
    aog_event_cost_usd: float = 100_000   # one aircraft-on-ground event (for context)
    calibration_limit: float = 60         # proposed calibration-load trigger
    tension_limit_pct: float = 6          # proposed re-tension trigger
    inspection_top_pct: float = 5         # share of screenings that get a detailed inspection
    ai_tier: str = "standard"             # standard | premium

    def as_dict(self) -> dict:
        return asdict(self)


def _span_years(data) -> float:
    d = data.train[config.DATE_COLUMN]
    return (d.max() - d.min()).days / 365


def _scale(data, a: Assumptions) -> float:
    """Multiply dataset counts by this to get counts per year for the planned fleet."""
    return (a.fleet_aircraft / DATA_AIRCRAFT) / _span_years(data)


def _usd(x) -> int:
    return int(round(float(x)))


def _pct(x, digits=1):
    return round(float(x) * 100, digits)


# --------------------------------------------------------------------------- problems (root cause)
def problem_register(data) -> dict:
    """The measured business problems, each with its share of defects."""
    tr = data.train
    y = tr[config.LABEL_COLUMN]
    total = int(y.sum())
    overdue = tr.calibration_overdue
    bad_tension = tr.Tension_Dev_Abs_Pct > 6
    hot = tr.Ambient_Temperature_C > 35
    fresh = tr.Calib_Load <= 30
    return {
        "training_defects": total, "training_screenings": int(len(tr)),
        "problems": [
            {"problem": "Tension tools used while overdue for calibration",
             "defects_involved": int(y[overdue].sum()), "share_of_defects_pct": _pct(y[overdue].sum() / total),
             "defect_rate_overdue_pct": _pct(y[overdue].mean()), "defect_rate_fresh_tool_pct": _pct(y[fresh].mean())},
            {"problem": "Belts tensioned more than 6% off target",
             "share_of_screenings_pct": _pct(bad_tension.mean()),
             "share_of_defects_pct": _pct(y[bad_tension].sum() / total),
             "defect_rate_pct": _pct(y[bad_tension].mean())},
            {"problem": "Hot-season operation (ambient above 35 C)",
             "defect_rate_hot_pct": _pct(y[hot].mean()), "defect_rate_other_pct": _pct(y[~hot].mean())},
            {"problem": "No early warning: the same calibration lapse repeated on three tools",
             "tools_with_past_lapses": ["Tool-05", "Tool-01"], "tool_lapsing_now": "Tool-03"},
        ],
    }


def tension_calibration_matrix(data) -> dict:
    tr = data.train
    y = tr[config.LABEL_COLUMN]
    rows = []
    for overdue in (False, True):
        for bad in (False, True):
            m = (tr.calibration_overdue == overdue) & ((tr.Tension_Dev_Abs_Pct > 6) == bad)
            rows.append({"tool_overdue": overdue, "tension_over_6pct": bad, "screenings": int(m.sum()),
                         "defect_rate_pct": _pct(y[m].mean()), "share_of_defects_pct": _pct(y[m].sum() / y.sum())})
    return {"source": "training data, actual outcomes", "cells": rows}


def supplier_tool_interaction(data) -> dict:
    tr = data.train
    g = tr.groupby(["Belt_Supplier", "calibration_overdue"])[config.LABEL_COLUMN].agg(["mean", "size"])
    return {"source": "training data, actual outcomes",
            "note": "compares suppliers with and without an overdue tool",
            "groups": [{"supplier": s, "tool_overdue": bool(o), "defect_rate_pct": _pct(r["mean"]),
                        "screenings": int(r["size"])} for (s, o), r in g.iterrows()]}


# --------------------------------------------------------------------------- Fix 1: calibration policy
def _calibration_cycles(train: pd.DataFrame) -> list:
    """Max calibration load reached in each tool's calibration cycle."""
    cycles = []
    for _, g in train.sort_values(config.DATE_COLUMN).groupby("Tool_ID"):
        days, load = g.Days_Since_Tool_Calibration.to_numpy(), g.Calib_Load.to_numpy()
        starts = [0] + list(np.where(np.diff(days) < -10)[0] + 1) + [len(g)]
        cycles += [float(np.nanmax(load[a:b])) for a, b in zip(starts[:-1], starts[1:]) if b > a]
    return cycles


def calibration_policy_options(data, a: Assumptions) -> dict:
    """For each calibration-load trigger: defects avoided, extra calibrations, net value per year."""
    tr = data.train
    y = tr[config.LABEL_COLUMN]
    fresh_rate = y[tr.Calib_Load <= 30].mean()
    cycles = _calibration_cycles(tr)
    scale = _scale(data, a)
    tool_scale = (a.fleet_aircraft / DATA_AIRCRAFT) / _span_years(data)
    limits = sorted({30, 45, 60, 90, a.calibration_limit})
    excess_by_limit, running = {}, 0.0
    for limit in reversed(limits):        # a tighter limit can never avoid fewer defects than a looser one
        over = tr.Calib_Load > limit
        running = max(running, y[over].sum() - over.sum() * fresh_rate, 0)
        excess_by_limit[limit] = running
    options = []
    for limit in limits:
        # load grows ~ days x uses ~ days^2, so a cycle that peaked at L needs ~sqrt(L/limit) calibrations
        extra = sum(max(math.ceil(math.sqrt(peak / limit)) - 1, 0) for peak in cycles if peak > limit)
        avoided, extra_cal = excess_by_limit[limit] * scale, extra * tool_scale
        value = avoided * a.cost_per_defect_usd
        cost = extra_cal * a.calibration_cost_usd
        options.append({"calibration_load_limit": limit, "defects_avoided_per_year": round(avoided),
                        "extra_calibrations_per_year": round(extra_cal), "annual_value_usd": _usd(value),
                        "annual_cost_usd": _usd(cost), "net_annual_value_usd": _usd(value - cost)})
    return {"fleet_aircraft": a.fleet_aircraft, "fresh_tool_defect_rate_pct": _pct(fresh_rate),
            "current_overdue_rule": f"load above {fa.OVERDUE_CALIBRATION_LOAD}",
            "typical_load_at_calibration_today": round(float(np.median(cycles)), 1), "options": options}


def tools_at_risk_now(data) -> dict:
    t = fa.tool_summary(data)
    load_now = (t.days_since_calibration * t.uses_since_calibration / 1000).round(0)
    return {"latest_month": f"{data.test.month.max():%Y-%m}", "tools": [{
        "tool": r.Tool_ID, "calibration_load_now": float(l), "days_since_calibration": float(r.days_since_calibration),
        "latest_avg_tension_difference_pct": round(float(r.latest_tension_error), 1),
        "latest_month_predicted_defect_rate_pct": _pct(r.latest_predicted_rate),
    } for r, l in zip(t.itertuples(), load_now)]}


# --------------------------------------------------------------------------- Fix 2: tension check
def tension_check_policy(data, a: Assumptions) -> dict:
    tr = data.train
    y = tr[config.LABEL_COLUMN]
    screenings_per_year = len(tr) * _scale(data, a)
    options = []
    for limit in sorted({4, 6, 8, a.tension_limit_pct}):
        m = tr.Tension_Dev_Abs_Pct > limit
        n = m.mean() * screenings_per_year
        options.append({"retension_if_off_by_more_than_pct": limit, "share_of_screenings_pct": _pct(m.mean()),
                        "share_of_defects_covered_pct": _pct(y[m].sum() / y.sum()),
                        "retensions_per_year": round(n), "annual_cost_usd": _usd(n * a.retension_cost_usd)})
    return {"fleet_aircraft": a.fleet_aircraft, "note": "overlaps with the calibration fix; safety net, not extra value",
            "options": options}


# --------------------------------------------------------------------------- Fix 3: risk-based inspection
def inspection_capture_curve(data, a: Assumptions) -> dict:
    """Inspect the top X% of screenings by model risk: defects caught and cost per year (out-of-fold scores)."""
    y = data.train[config.LABEL_COLUMN].to_numpy()
    oof = np.load(config.METRICS_DIR / "oof_probabilities.npy")
    order = np.argsort(-oof)
    screenings_per_year = len(y) * _scale(data, a)
    defects_per_year = y.sum() * _scale(data, a)
    rows = []
    for pct in sorted({1, 2, 3, 5, 10, 20, a.inspection_top_pct}):
        k = int(round(pct / 100 * len(y)))
        caught = y[order[:k]].sum()
        n = pct / 100 * screenings_per_year
        rows.append({"inspect_top_pct": pct, "inspections_per_year": round(n),
                     "defects_caught_pct": _pct(caught / y.sum()), "defects_found_per_100_inspections": round(
                         caught / k * 100, 1), "annual_cost_usd": _usd(n * a.inspection_cost_usd)})
    return {"fleet_aircraft": a.fleet_aircraft, "screenings_per_year": round(screenings_per_year),
            "defects_per_year": round(defects_per_year),
            "random_inspection_defects_per_100": round(y.mean() * 100, 1),
            "blanket_inspection_cost_usd": _usd(screenings_per_year * a.inspection_cost_usd), "options": rows}


# --------------------------------------------------------------------------- Fix 4: season planning
def season_plan(data, a: Assumptions) -> dict:
    tr, te = data.train, data.test
    y = tr[config.LABEL_COLUMN]
    fleet_factor = a.fleet_aircraft / DATA_AIRCRAFT
    months = te.groupby("month").agg(predicted=("predicted_defect", "sum"), screenings=("predicted_defect", "size"))
    spring = tr[tr.month.dt.month.isin([4, 5])].groupby(tr.month.dt.year)[config.LABEL_COLUMN].mean()
    return {"fleet_aircraft": a.fleet_aircraft,
            "defect_rate_hot_pct": _pct(y[tr.Ambient_Temperature_C > 35].mean()),
            "defect_rate_other_pct": _pct(y[~(tr.Ambient_Temperature_C > 35)].mean()),
            "apr_may_defect_rate_pct_by_year": {str(k): _pct(v) for k, v in spring.items()},
            "predicted_month_view": [{"month": f"{m:%Y-%m}", "predicted_defect_rate_pct": _pct(r.predicted / r.screenings),
                                      "predicted_belt_replacements_for_fleet": round(r.predicted * fleet_factor)}
                                     for m, r in months.iterrows()],
            "note": "the first test month is partial; use rates, not counts, for it"}


# --------------------------------------------------------------------------- finance
TOKEN_UNIT_COST = {"standard": dict(briefing=0.05, question=0.001, check=0.0005, report=0.50),
                   "premium": dict(briefing=0.50, question=0.01, check=0.005, report=5.00)}


def enterprise_cost(data, a: Assumptions) -> dict:
    """Token cost (scaled from measured runs) plus total cost of ownership ranges for the planned business."""
    tier = a.ai_tier if a.ai_tier in TOKEN_UNIT_COST else "standard"
    u = TOKEN_UNIT_COST[tier]
    groups = max(round(a.fleet_aircraft / 100), 1)
    screenings_month = len(data.train) * _scale(data, a) / 12
    volume = {"fleet_briefings": groups * 24 * 30, "base_briefings": a.bases * 3 * 30,
              "questions": a.users * 15 * 22, "screening_checks": round(screenings_month), "reports": groups * 4}
    monthly = (volume["fleet_briefings"] * u["briefing"] + volume["base_briefings"] * u["briefing"]
               + volume["questions"] * u["question"] + volume["screening_checks"] * u["check"]
               + volume["reports"] * u["report"])
    size = a.fleet_aircraft / 1000
    tco_low = 17_000 * (monthly / 968) + (50_000 + 60_000 + 80_000) * max(size, 0.2) + 30_000 + 450_000
    tco_high = 17_000 * (monthly / 968) * 1.5 + (250_000 + 150_000 + 150_000) * max(size, 0.2) + 60_000 + 700_000
    return {"ai_tier": tier, "monthly_volume": volume, "ai_tokens_per_month_usd": _usd(monthly),
            "ai_tokens_per_year_with_headroom_usd": _usd(monthly * 12 * 1.5),
            "total_cost_of_ownership_per_year_usd": {"low": _usd(tco_low), "high": _usd(tco_high)},
            "integration_one_off_usd": {"low": _usd(200_000 * max(size, 0.25)), "high": _usd(500_000 * max(size, 0.25))},
            "tco_includes": ["team 3-4 FTE", "enterprise AI platform", "hosting and MLOps",
                             "security and compliance", "maintenance-system integration upkeep", "AI tokens"]}


CALIBRATION_LIMITS = [30, 45, 60, 75, 90]
TENSION_LIMITS = [4, 6, 8]
INSPECTION_TOP_PCTS = [1, 2, 3, 5, 10, 20]


def business_value(data, a: Assumptions, calibration_limit: float | None = None,
                   tension_limit_pct: float | None = None, inspection_top_pct: float | None = None) -> dict:
    """Value, cost, net benefit, return and payback for a policy choice (defaults = the user's assumptions)."""
    a = replace(a, calibration_limit=float(calibration_limit or a.calibration_limit),
                tension_limit_pct=float(tension_limit_pct or a.tension_limit_pct),
                inspection_top_pct=float(inspection_top_pct or a.inspection_top_pct))
    cal = next(o for o in calibration_policy_options(data, a)["options"]
               if o["calibration_load_limit"] == a.calibration_limit)
    ten = next(o for o in tension_check_policy(data, a)["options"]
               if o["retension_if_off_by_more_than_pct"] == a.tension_limit_pct)
    insp = inspection_capture_curve(data, a)
    chosen = next(o for o in insp["options"] if o["inspect_top_pct"] == a.inspection_top_pct)
    cost = enterprise_cost(data, a)
    tco, one_off = cost["total_cost_of_ownership_per_year_usd"], cost["integration_one_off_usd"]

    core_low = cal["net_annual_value_usd"] - tco["high"]          # calibration fix pays for the whole system
    core_high = cal["net_annual_value_usd"] - tco["low"]
    programme = ten["annual_cost_usd"] + chosen["annual_cost_usd"]

    def payback_months(net_per_year, one_off_usd):
        return round(one_off_usd / (net_per_year / 12), 1) if net_per_year > 0 else None

    return {
        "policy": {"calibration_limit": a.calibration_limit, "tension_limit_pct": a.tension_limit_pct,
                   "inspection_top_pct": a.inspection_top_pct, "fleet_aircraft": a.fleet_aircraft},
        "fix_1_calibration": cal,
        "fix_2_tension_check": ten,
        "fix_3_inspection": {**chosen, "saving_vs_blanket_inspection_usd":
                             _usd(insp["blanket_inspection_cost_usd"] - chosen["annual_cost_usd"])},
        "system_cost": {"tco_per_year_low_usd": tco["low"], "tco_per_year_high_usd": tco["high"],
                        "integration_one_off_low_usd": one_off["low"], "integration_one_off_high_usd": one_off["high"],
                        "ai_tokens_per_year_usd": cost["ai_tokens_per_year_with_headroom_usd"]},
        "net_benefit_per_year_after_system_cost_usd": {"low": _usd(core_low), "high": _usd(core_high)},
        "net_benefit_per_year_after_system_and_programme_costs_usd": {"low": _usd(core_low - programme),
                                                                      "high": _usd(core_high - programme)},
        "return_multiple_on_system_cost": {"low": round(cal["net_annual_value_usd"] / tco["high"], 1),
                                           "high": round(cal["net_annual_value_usd"] / tco["low"], 1)},
        "payback_months_on_integration": {"best": payback_months(core_high, one_off["low"]),
                                          "worst": payback_months(core_low, one_off["high"])},
        "notes": ["Value counts the calibration fix only (measured defects avoided).",
                  "Tension checks overlap the calibration fix (safety net); not added to value.",
                  "Risk-based inspection is a cost with a saving versus blanket inspection; not added to value.",
                  "Programme costs = tension checks + targeted inspections.",
                  "Dollar figures depend on the unit-cost assumptions."],
    }
