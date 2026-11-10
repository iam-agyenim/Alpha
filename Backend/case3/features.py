"""Cleaning and feature engineering. Every feature is built from one row only (no joins across rows),
as the problem statement requires, so the same function serves training and test data."""
from __future__ import annotations

import pandas as pd
import numpy as np

TARGET = "Defect_Found"
ID = "Record_ID"

CATEGORICAL = ["Maintenance_Station", "Technician_ID", "Tool_ID", "Belt_Supplier", "Belt_Batch_ID"]
NUMERIC = [
    "High_Load_Hours_Last_30_Days", "Hot_Operation_Days_Last_30_Days", "Peak_Operating_Temperature_C",
    "Days_Since_Tool_Calibration", "Tool_Uses_Since_Calibration", "Belt_Age_Hours", "Cycles_Since_Belt_Install",
    "Belt_Target_Tension_N", "Belt_Measured_Tension_N", "Ambient_Temperature_C", "Relative_Humidity_Pct",
    "Engine_Load_Ratio", "Alignment_Offset_mm", "Contamination_Index", "Operating_Hours_Last_30_Days",
    "Belt_Temperature_C", "Belt_Vibration_mm_s", "Belt_Slip_Pct",
]
# Identifiers and the date are not model inputs: tags do not define a shared history (problem statement), and an
# absolute date would only teach the model the training period's calendar.
NOT_INPUTS = [ID, "Aircraft_ID", "Engine_ID", "Maintenance_Date", TARGET]

_CANON = {"STATION": "Station", "SUPPLIER": "Supplier", "TOOL": "Tool", "TECH": "TECH"}


def _canon_cat(s: pd.Series) -> pd.Series:
    """'  station a ', 'tool-05 ' -> 'Station A', 'Tool-05' (the raw files mix case and stray spaces)."""
    out = s.astype("string").str.strip().str.upper()
    for up, nice in _CANON.items():
        out = out.str.replace(rf"^{up}", nice, regex=True)
    return out


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in CATEGORICAL + ["Aircraft_ID", "Engine_ID"]:
        if c in df:
            df[c] = _canon_cat(df[c])
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["Maintenance_Date"] = pd.to_datetime(df["Maintenance_Date"], errors="coerce")
    if TARGET in df:
        df[TARGET] = df[TARGET].astype("string").str.strip().str.capitalize()
    return df


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Domain features. All are ratios/differences of columns in the same row."""
    df = df.copy()
    tgt, meas = df["Belt_Target_Tension_N"], df["Belt_Measured_Tension_N"]
    df["Tension_Diff_N"] = meas - tgt
    df["Tension_Diff_Pct"] = (meas - tgt) / tgt * 100
    df["Abs_Tension_Diff_Pct"] = df["Tension_Diff_Pct"].abs()
    df["Belt_Minus_Ambient_C"] = df["Belt_Temperature_C"] - df["Ambient_Temperature_C"]
    df["High_Load_Share"] = df["High_Load_Hours_Last_30_Days"] / df["Operating_Hours_Last_30_Days"]
    df["Tool_Uses_Per_Day"] = df["Tool_Uses_Since_Calibration"] / df["Days_Since_Tool_Calibration"].replace(0, np.nan)
    df["Hours_Per_Cycle"] = df["Belt_Age_Hours"] / df["Cycles_Since_Belt_Install"].replace(0, np.nan)
    df["Vib_x_Temp"] = df["Belt_Vibration_mm_s"] * df["Belt_Temperature_C"]
    df["Slip_x_AbsTension"] = df["Belt_Slip_Pct"] * df["Abs_Tension_Diff_Pct"]
    df["Month_Of_Year"] = df["Maintenance_Date"].dt.month
    df["N_Missing"] = df[NUMERIC].isna().sum(axis=1)
    return df


ENGINEERED = ["Tension_Diff_N", "Tension_Diff_Pct", "Abs_Tension_Diff_Pct", "Belt_Minus_Ambient_C", "High_Load_Share",
              "Tool_Uses_Per_Day", "Hours_Per_Cycle", "Vib_x_Temp", "Slip_x_AbsTension", "Month_Of_Year", "N_Missing"]


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    return add_features(clean(df))


def target(df: pd.DataFrame) -> np.ndarray:
    return (df[TARGET] == "Yes").to_numpy(dtype=int)
