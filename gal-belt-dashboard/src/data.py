"""Load, validate and normalise belt maintenance records.

Everything downstream works on the canonical column names defined here, so a
file with slightly different headers or labels still runs through the app.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "gal_belt_data.csv"

# Known before the job starts -> legitimate predictors.
LEADING = ["Tool_ID", "Tool_Status", "Maintenance_Station", "Month"]
# Recorded at the same inspection as the defect -> symptoms, never predictors.
SYMPTOMS = ["Belt_Condition", "Belt_Temperature", "Belt_Vibration"]
TARGET = "Belt_Defect"
IDS = ["Record_ID", "Aircraft_ID"]

REQUIRED = LEADING + [TARGET]
CANONICAL = IDS + LEADING + SYMPTOMS + [TARGET]

FACTOR_LABELS = {
    "Tool_ID": "Tool",
    "Tool_Status": "Tool status",
    "Maintenance_Station": "Station",
    "Month": "Month",
    "Belt_Condition": "Belt condition",
    "Belt_Temperature": "Belt temperature",
    "Belt_Vibration": "Belt vibration",
}

NORMAL_STATUS = "Normal"
CAL_STATUS = "Needs Calibration"

# Header aliases, keyed by the header lower-cased with all non-letters removed.
_COLUMN_ALIASES = {
    "recordid": "Record_ID", "record": "Record_ID", "id": "Record_ID", "jobid": "Record_ID",
    "aircraftid": "Aircraft_ID", "aircraft": "Aircraft_ID", "tailnumber": "Aircraft_ID", "tail": "Aircraft_ID",
    "month": "Month", "date": "Month",
    "maintenancestation": "Maintenance_Station", "station": "Maintenance_Station",
    "toolid": "Tool_ID", "tool": "Tool_ID",
    "toolstatus": "Tool_Status", "calibrationstatus": "Tool_Status",
    "beltcondition": "Belt_Condition", "condition": "Belt_Condition",
    "belttemperature": "Belt_Temperature", "temperature": "Belt_Temperature", "belttemp": "Belt_Temperature",
    "beltvibration": "Belt_Vibration", "vibration": "Belt_Vibration",
    "beltdefect": "Belt_Defect", "defect": "Belt_Defect",
}

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_YES = {"yes", "y", "true", "t", "1", "defect", "defective", "fail", "failed"}
_NO = {"no", "n", "false", "f", "0", "none", "ok", "pass", "passed"}
_STATUS_NORMAL = {"normal", "ok", "calibrated", "valid", "incalibration", "good", "serviceable", "current"}
_STATUS_CAL = {"needscalibration", "needcalibration", "due", "overdue", "calibrationdue", "calibrationoverdue",
               "expired", "outofcalibration", "uncalibrated", "requirescalibration", "notcalibrated"}
_HIGH = {"high", "abnormal", "elevated", "excessive", "hi"}
_NORMAL_LEVEL = {"normal", "ok", "low", "good", "nominal"}
_ABNORMAL = {"abnormal", "bad", "worn", "damaged", "high", "poor", "cracked"}


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


@dataclass
class LoadResult:
    df: pd.DataFrame | None
    missing: list[str] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)
    source: str = ""

    @property
    def ok(self) -> bool:
        return self.df is not None and not self.missing and len(self.df) > 0


def read_raw(source=None, filename: str | None = None) -> tuple[pd.DataFrame, str]:
    """Read a CSV/XLSX from a path, bytes or file-like object (default: bundled CSV)."""
    if source is None:
        return pd.read_csv(DEFAULT_DATA, dtype=str), DEFAULT_DATA.name
    name = filename or getattr(source, "name", None) or str(source)
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    if str(name).lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(source, dtype=str), Path(str(name)).name
    return pd.read_csv(source, dtype=str), Path(str(name)).name


def month_label(value) -> str | None:
    """Turn 'Jan', 'january', '1', '2026-01-15' into 'Jan'."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    k = _key(text)
    for m in _MONTHS:
        if k.startswith(m.lower()):
            return m
    if text.isdigit() and 1 <= int(text) <= 12:
        return _MONTHS[int(text) - 1]
    try:
        ts = pd.to_datetime(text)
        return _MONTHS[ts.month - 1]
    except (ValueError, TypeError):
        return text


def month_order(values) -> list[str]:
    """Calendar order for the month labels present; unknown labels go last."""
    present = list(dict.fromkeys(v for v in values if v is not None))
    known = [m for m in _MONTHS if m in present]
    return known + sorted(v for v in present if v not in _MONTHS)


def _map_values(series: pd.Series, mapping: list[tuple[set, str]]) -> tuple[pd.Series, int]:
    changed = 0

    def convert(v):
        nonlocal changed
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        k = _key(v)
        for keys, label in mapping:
            if k in keys:
                if str(v).strip() != label:
                    changed += 1
                return label
        clean = re.sub(r"\s+", " ", str(v).strip())
        if clean != v:
            changed += 1
        return clean

    return series.map(convert), changed


def normalise(raw: pd.DataFrame, source: str = "") -> LoadResult:
    log: list[dict] = []
    df = raw.copy()

    # 1. Column names
    rename = {}
    for col in df.columns:
        target = _COLUMN_ALIASES.get(_key(col))
        if target and target not in rename.values():
            rename[col] = target
    renamed = {k: v for k, v in rename.items() if k != v}
    if renamed:
        log.append({"step": "Column names", "detail": ", ".join(f"'{k}' → {v}" for k, v in renamed.items())})
    df = df.rename(columns=rename)

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        return LoadResult(None, missing, log, source)

    keep = [c for c in CANONICAL if c in df.columns]
    df = df[keep].astype(object)
    log.append({"step": "Rows read", "detail": f"{len(df)} rows, {len(keep)} recognised columns"})

    # 2. Strip whitespace everywhere and turn blanks into missing
    for c in keep:
        df[c] = df[c].map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v))
                          or str(v).strip() == "" else re.sub(r"\s+", " ", str(v).strip()))

    # 3. IDs
    if "Record_ID" not in df.columns:
        df["Record_ID"] = [f"R{i + 1:03d}" for i in range(len(df))]
        log.append({"step": "Record_ID", "detail": "Column missing: generated R001, R002, ..."})
    if "Aircraft_ID" not in df.columns:
        df["Aircraft_ID"] = "Unknown"
        log.append({"step": "Aircraft_ID", "detail": "Column missing: set to 'Unknown'"})

    # 4. Labels
    df[TARGET], n = _map_values(df[TARGET], [(_YES, "Yes"), (_NO, "No")])
    if n:
        log.append({"step": "Belt_Defect labels", "detail": f"{n} values mapped to Yes/No"})
    df["Tool_Status"], n = _map_values(df["Tool_Status"], [(_STATUS_NORMAL, NORMAL_STATUS), (_STATUS_CAL, CAL_STATUS)])
    if n:
        log.append({"step": "Tool_Status labels", "detail": f"{n} values mapped to Normal/Needs Calibration"})
    for c, mapping in [("Belt_Temperature", [(_HIGH, "High"), (_NORMAL_LEVEL, "Normal")]),
                       ("Belt_Vibration", [(_HIGH, "High"), (_NORMAL_LEVEL, "Normal")]),
                       ("Belt_Condition", [(_ABNORMAL, "Abnormal"), (_NORMAL_LEVEL, "Normal")])]:
        if c in df.columns:
            df[c], n = _map_values(df[c], mapping)
            if n:
                log.append({"step": f"{c} labels", "detail": f"{n} values standardised"})
    before = df["Month"].copy()
    df["Month"] = df["Month"].map(month_label)
    n = int((before.fillna("") != df["Month"].fillna("")).sum())
    if n:
        log.append({"step": "Month labels", "detail": f"{n} values converted to 3-letter month names"})

    # 5. Missing values
    missing_counts = {c: int(df[c].isna().sum()) for c in df.columns if df[c].isna().any()}
    log.append({"step": "Missing values",
                "detail": ", ".join(f"{c}: {n}" for c, n in missing_counts.items()) if missing_counts else "None"})
    bad_target = df[TARGET].isin(["Yes", "No"]) == False  # noqa: E712
    drop = df[REQUIRED].isna().any(axis=1) | bad_target
    if drop.any():
        log.append({"step": "Rows dropped",
                    "detail": f"{int(drop.sum())} rows with a missing required value or an unreadable defect label"})
        df = df[~drop]
    for c in SYMPTOMS:
        if c in df.columns and df[c].isna().any():
            df[c] = df[c].fillna("Unknown")

    dupes = int(df["Record_ID"].duplicated().sum())
    if dupes:
        log.append({"step": "Duplicates", "detail": f"{dupes} duplicate Record_IDs (kept, check the source)"})

    df = df.reset_index(drop=True)
    df["defect"] = (df[TARGET] == "Yes").astype(int)
    return LoadResult(df, [], log, source)


def load(source=None, filename: str | None = None) -> LoadResult:
    try:
        raw, name = read_raw(source, filename)
    except Exception as exc:  # unreadable file: report, don't crash
        return LoadResult(None, [], [{"step": "Read error", "detail": str(exc)}], str(filename or source))
    return normalise(raw, name)


def summary(df: pd.DataFrame) -> dict:
    return {
        "records": len(df),
        "aircraft": int(df["Aircraft_ID"].nunique()),
        "defects": int(df["defect"].sum()),
        "months": month_order(df["Month"].unique()),
    }
