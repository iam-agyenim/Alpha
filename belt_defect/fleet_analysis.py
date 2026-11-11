"""Fleet-level analysis behind the dashboard.

Training rows carry actual outcomes; test rows (the latest period) carry model predictions.
All numbers show association with defects, not proven cause.
"""
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config
from .feature_engineering import build_features
from .preprocessing import clean_raw_data, load_test_inputs, load_training_data

# --- Thresholds used across the dashboard ---
NORMAL_RANGE_QUANTILE = 0.99      # "abnormal" = outside 99% of defect-free training screenings
MEDIUM_RISK_PROBABILITY = 0.20    # below the Yes threshold, but well above the ~3% base rate
OVERDUE_CALIBRATION_LOAD = 90     # days x uses since calibration / 1000; defect rate ~19% above this
ELEVATED_TENSION_PCT = 6          # |tension error| above this: defect rate ~7%+ (vs ~0.5% below 2%)

STATUS_HIGH, STATUS_MEDIUM, STATUS_NORMAL = "High Risk", "Medium", "Normal"
STATUS_ORDER = [STATUS_HIGH, STATUS_MEDIUM, STATUS_NORMAL]

# Measurement column -> (label, unit) for the abnormal-measurement checks
MEASUREMENTS = {
    "Tension_Dev_Abs_Pct": ("Tension difference", "%"),
    "Belt_Vibration_mm_s": ("Vibration", " mm/s"),
    "Belt_Temperature_C": ("Belt temperature", " °C"),
    "Belt_Slip_Pct": ("Belt slip", "%"),
}


@dataclass
class FleetData:
    train: pd.DataFrame          # actual outcomes (is_defect)
    test: pd.DataFrame           # predictions (defect_probability, predicted_defect)
    threshold: float             # Yes/No cut-off chosen on training data
    oof_metrics: dict            # cross-validated scores of the final model
    normal_limits: dict          # measurement -> upper limit of the normal range


def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add the engineered columns the dashboard reports on."""
    features = build_features(df)
    df = df.copy()
    for col in ["Tension_Dev_Pct", "Tension_Dev_Abs_Pct", "Calib_Load"]:
        df[col] = features[col]
    df["calibration_overdue"] = df.Calib_Load > OVERDUE_CALIBRATION_LOAD
    df["month"] = df[config.DATE_COLUMN].dt.to_period("M").dt.to_timestamp()
    return df


def normal_measurement_limits(train: pd.DataFrame) -> dict:
    """Upper limit of the normal range for each measurement, from defect-free training rows."""
    healthy = train[train[config.LABEL_COLUMN] == 0]
    return {col: float(healthy[col].quantile(NORMAL_RANGE_QUANTILE)) for col in MEASUREMENTS}


def flag_abnormal_measurements(df: pd.DataFrame, limits: dict) -> pd.DataFrame:
    """Add one flag per measurement, an overall flag and a readable list of what is abnormal."""
    df = df.copy()
    for col in MEASUREMENTS:
        df[f"abnormal_{col}"] = df[col] > limits[col]
    flag_cols = [f"abnormal_{c}" for c in MEASUREMENTS]
    df["abnormal_any"] = df[flag_cols].any(axis=1)
    return df


def load_fleet_data() -> FleetData:
    """Load training data, test inputs and saved model outputs (run train_and_predict.py first)."""
    probabilities_path = config.PREDICTIONS_DIR / "test_probabilities.csv"
    metrics_path = config.METRICS_DIR / "oof_metrics.json"
    if not probabilities_path.exists() or not metrics_path.exists():
        raise FileNotFoundError("Model outputs missing. Run: .venv/bin/python scripts/train_and_predict.py")

    oof_metrics = json.loads(metrics_path.read_text())
    threshold = oof_metrics["threshold"]

    train = _add_derived_columns(load_training_data(config.TRAIN_PATH, sort_by_date=True))
    test = clean_raw_data(load_test_inputs(config.TEST_INPUTS_PATH))
    test = _add_derived_columns(test.merge(pd.read_csv(probabilities_path), on=config.ID_COLUMN))
    test["predicted_defect"] = test.defect_probability >= threshold

    limits = normal_measurement_limits(train)
    return FleetData(flag_abnormal_measurements(train, limits), flag_abnormal_measurements(test, limits),
                     threshold, oof_metrics, limits)


# --------------------------------------------------------------------------- trends
def monthly_defect_trend(data: FleetData) -> pd.DataFrame:
    """Monthly defect rate: actual for training months, predicted for test months."""
    def summarize(df, label_col, source):
        g = df.groupby("month").agg(
            defect_rate=(label_col, "mean"), screenings=(label_col, "size"),
            ambient_temp=("Ambient_Temperature_C", "mean"),
            overdue_share=("calibration_overdue", "mean"),
            tension_error=("Tension_Dev_Abs_Pct", "mean"),
        ).reset_index()
        g["source"] = source
        return g

    return pd.concat([summarize(data.train, config.LABEL_COLUMN, "Actual"),
                      summarize(data.test, "predicted_defect", "Predicted")], ignore_index=True)


# --------------------------------------------------------------------------- factors
def defect_rate_by(df: pd.DataFrame, column, label_col=config.LABEL_COLUMN) -> pd.DataFrame:
    """Defect rate and count per group, sorted by rate."""
    g = df.groupby(column, observed=True)[label_col].agg(defect_rate="mean", screenings="size").reset_index()
    return g.sort_values("defect_rate", ascending=False)


def defect_rate_by_tension_band(train: pd.DataFrame) -> pd.DataFrame:
    """Defect rate by size of tension error (measured vs target)."""
    bands = pd.cut(train.Tension_Dev_Abs_Pct, [0, 2, 4, 6, 8, 10, np.inf],
                   labels=["0–2%", "2–4%", "4–6%", "6–8%", "8–10%", ">10%"], include_lowest=True)
    return defect_rate_by(train.assign(tension_band=bands), "tension_band").sort_values("tension_band")


def abnormal_measurement_lift(train: pd.DataFrame) -> pd.DataFrame:
    """Defect rate when each measurement is outside vs inside its normal range."""
    rows = []
    for col, (label, _) in MEASUREMENTS.items():
        flag = train[f"abnormal_{col}"]
        rows.append(dict(measurement=label,
                         rate_abnormal=train.loc[flag, config.LABEL_COLUMN].mean(),
                         rate_normal=train.loc[~flag, config.LABEL_COLUMN].mean(),
                         abnormal_screenings=int(flag.sum())))
    out = pd.DataFrame(rows)
    out["times_more_likely"] = out.rate_abnormal / out.rate_normal
    return out.sort_values("times_more_likely", ascending=False)


# --------------------------------------------------------------------------- tools
def tool_summary(data: FleetData) -> pd.DataFrame:
    """Per tool: historical defect rate, current calibration state and predicted defect rate."""
    latest_month = data.test.month.max()
    hist = data.train.groupby("Tool_ID").agg(
        training_defect_rate=(config.LABEL_COLUMN, "mean"),
        training_overdue_share=("calibration_overdue", "mean"),
    )
    current = data.test.groupby("Tool_ID").agg(
        predicted_defect_rate=("predicted_defect", "mean"),
        current_overdue_share=("calibration_overdue", "mean"),
        screenings=("predicted_defect", "size"),
    )
    latest = data.test[data.test.month == latest_month].groupby("Tool_ID").agg(
        days_since_calibration=("Days_Since_Tool_Calibration", "max"),
        uses_since_calibration=("Tool_Uses_Since_Calibration", "max"),
        latest_tension_error=("Tension_Dev_Pct", "mean"),
        latest_predicted_rate=("predicted_defect", "mean"),
    )
    return hist.join(current).join(latest).reset_index().sort_values("latest_predicted_rate", ascending=False)


def tool_monthly_drift(data: FleetData, tool_id: str) -> pd.DataFrame:
    """One tool over time: days since calibration, signed tension error and defect rate."""
    both = pd.concat([data.train.assign(defect=data.train[config.LABEL_COLUMN], source="Actual"),
                      data.test.assign(defect=data.test.predicted_defect.astype(int), source="Predicted")])
    tool = both[both.Tool_ID == tool_id]
    return tool.groupby(["month", "source"]).agg(
        days_since_calibration=("Days_Since_Tool_Calibration", "mean"),
        tension_error=("Tension_Dev_Pct", "mean"),
        defect_rate=("defect", "mean"),
    ).reset_index()


def defect_rate_by_calibration(train: pd.DataFrame) -> pd.DataFrame:
    """Defect rate by calibration load band."""
    bands = pd.cut(train.Calib_Load, [-np.inf, 30, 60, OVERDUE_CALIBRATION_LOAD, np.inf],
                   labels=["<30", "30–60", "60–90", ">90 (overdue)"])
    return defect_rate_by(train.assign(calibration_band=bands), "calibration_band").sort_values("calibration_band")


def problem_tool(tools: pd.DataFrame) -> pd.Series:
    """Tool most associated with current predicted defects (highest latest-month predicted rate)."""
    return tools.iloc[0]


# --------------------------------------------------------------------------- aircraft
def screening_reasons(row: pd.Series, limits: dict) -> str:
    """Plain-language reasons a screening looks risky."""
    reasons = []
    for col, (label, unit) in MEASUREMENTS.items():
        if row[f"abnormal_{col}"]:
            value = row.Tension_Dev_Pct if col == "Tension_Dev_Abs_Pct" else row[col]
            sign = "+" if col == "Tension_Dev_Abs_Pct" else ""
            reasons.append(f"{label} {value:{sign}.1f}{unit} (normal ≤ {limits[col]:.1f}{unit})")
    if not row["abnormal_Tension_Dev_Abs_Pct"] and row.Tension_Dev_Abs_Pct > ELEVATED_TENSION_PCT:
        reasons.append(f"Tension difference {row.Tension_Dev_Pct:+.1f}% (elevated)")
    if row.calibration_overdue:
        reasons.append(f"{row.Tool_ID} overdue for calibration ({row.Days_Since_Tool_Calibration:.0f} days)")
    return "; ".join(reasons) or "Combination of factors (model)"


def belt_status(row: pd.Series) -> str:
    """High Risk = model predicts a defect; Medium = elevated risk or an abnormal measurement."""
    if row.predicted_defect:
        return STATUS_HIGH
    if row.defect_probability >= MEDIUM_RISK_PROBABILITY or row.abnormal_any:
        return STATUS_MEDIUM
    return STATUS_NORMAL


def aircraft_status(data: FleetData, window_days: int | None = None) -> pd.DataFrame:
    """One row per aircraft.

    window_days=None: each aircraft's latest screening (current belt state).
    window_days=N:    each aircraft's riskiest screening in the last N days.
    """
    test = data.test
    if window_days is None:
        chosen = test.sort_values(config.DATE_COLUMN).groupby("Aircraft_ID").tail(1)
    else:
        recent = test[test[config.DATE_COLUMN] >= test[config.DATE_COLUMN].max() - pd.Timedelta(days=window_days)]
        chosen = recent.sort_values("defect_probability").groupby("Aircraft_ID").tail(1)

    flagged_counts = test.groupby("Aircraft_ID").predicted_defect.sum()
    table = pd.DataFrame({
        "Aircraft": chosen.Aircraft_ID,
        "Belt Status": chosen.apply(belt_status, axis=1),
        "Tension Difference": chosen.Tension_Dev_Pct,
        "Tool": chosen.Tool_ID,
        "Engine": chosen.Engine_ID,
        "Screening date": chosen[config.DATE_COLUMN].dt.date,
        "Defect risk": chosen.defect_probability,
        "Why": chosen.apply(screening_reasons, axis=1, limits=data.normal_limits),
        "Flagged screenings (period)": chosen.Aircraft_ID.map(flagged_counts).astype(int),
        "Record_ID": chosen[config.ID_COLUMN],
    })
    table["status_rank"] = table["Belt Status"].map({s: i for i, s in enumerate(STATUS_ORDER)})
    return table.sort_values(["status_rank", "Defect risk"], ascending=[True, False]).drop(columns="status_rank") \
        .reset_index(drop=True)


def flagged_screenings(data: FleetData) -> pd.DataFrame:
    """Every test screening that is High Risk or Medium, with reasons (the inspection list)."""
    test = data.test.copy()
    test["Belt Status"] = test.apply(belt_status, axis=1)
    test = test[test["Belt Status"] != STATUS_NORMAL]
    test["Why"] = test.apply(screening_reasons, axis=1, limits=data.normal_limits)
    out = test[[config.ID_COLUMN, "Aircraft_ID", "Engine_ID", config.DATE_COLUMN, "Belt Status", "defect_probability",
                "Tension_Dev_Pct", "Tool_ID", "Maintenance_Station", "Why"]]
    return out.sort_values("defect_probability", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- alert text
def fleet_alert(aircraft: pd.DataFrame, tools: pd.DataFrame) -> dict:
    """Headline and contributing-factor sentence for the alert banner."""
    n_flagged = int((aircraft["Belt Status"] != STATUS_NORMAL).sum())
    n_high = int((aircraft["Belt Status"] == STATUS_HIGH).sum())
    tool = problem_tool(tools)
    others = tools[tools.Tool_ID != tool.Tool_ID]
    other_rate = float(np.average(others.latest_predicted_rate.fillna(0), weights=others.screenings))
    return dict(
        headline=f"{n_flagged} B787 aircraft have abnormal belt measurements.",
        detail=f"{n_high} are high risk and need inspection first.",
        factor=(f"Possible contributing factor: belt defects are more common when {tool.Tool_ID} is used. "
                f"It is {tool.days_since_calibration:.0f} days past calibration, belts it tensioned read "
                f"{tool.latest_tension_error:+.1f}% vs target, and {tool.latest_predicted_rate:.0%} of its latest jobs "
                f"are predicted defects (other tools: {other_rate:.0%})."),
        tool_id=tool.Tool_ID,
    )
