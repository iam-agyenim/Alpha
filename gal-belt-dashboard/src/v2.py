"""Release v2 data (the real GAL Case 3 files): detect, score with the trained model, summarise.

The model is trained offline by Backend/case3/train.py and saved to Backend/output/model.joblib; this module only
loads it and scores uploaded rows, so the dashboard never retrains. Every number shown in v2 mode comes from the
uploaded rows and the model's saved threshold.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[2] / "Backend"
MODEL_PATH = BACKEND / "output" / "model.joblib"
REPORT_PATH = BACKEND / "output" / "report.json"
IMPORTANCE_PATH = BACKEND / "output" / "feature_importance.csv"

# Columns that only the v2 schema has; two of them are enough to tell the formats apart.
MARKERS = {"Belt_Target_Tension_N", "Belt_Measured_Tension_N", "Days_Since_Tool_Calibration",
           "Tool_Uses_Since_Calibration", "Belt_Temperature_C", "Belt_Vibration_mm_s"}
TARGET, ID = "Defect_Found", "Record_ID"
BANDS = ["High Risk", "Medium", "Normal"]

LABELS = {
    "Belt_Age_Hours": "Belt age (h)", "Abs_Tension_Diff_Pct": "Tension off target (abs %)",
    "Tension_Diff_Pct": "Tension difference (%)", "Tension_Diff_N": "Tension difference (N)",
    "Peak_Operating_Temperature_C": "Peak operating temp (°C)", "Cycles_Since_Belt_Install": "Cycles since install",
    "Hot_Operation_Days_Last_30_Days": "Hot days, last 30", "Belt_Batch_ID": "Belt batch",
    "Belt_Temperature_C": "Belt temperature (°C)", "Vib_x_Temp": "Vibration × temperature",
    "Belt_Vibration_mm_s": "Vibration (mm/s)", "Days_Since_Tool_Calibration": "Days since tool calibration",
    "Tool_Uses_Since_Calibration": "Tool uses since calibration", "Slip_x_AbsTension": "Slip × tension error",
    "Belt_Slip_Pct": "Belt slip (%)", "Ambient_Temperature_C": "Ambient temp (°C)", "Tool_ID": "Tool",
    "Maintenance_Station": "Station", "Belt_Supplier": "Supplier", "Technician_ID": "Technician",
    "High_Load_Share": "High-load share", "Belt_Minus_Ambient_C": "Belt minus ambient (°C)",
}


def _backend_on_path() -> None:
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))


def read_raw(content: bytes | str | Path, name: str) -> pd.DataFrame:
    """CSV or Excel; for the training workbook, the 'Train Data' sheet."""
    src = io.BytesIO(content) if isinstance(content, bytes) else content
    if str(name).lower().endswith((".xlsx", ".xls")):
        sheets = pd.ExcelFile(src).sheet_names
        sheet = "Train Data" if "Train Data" in sheets else sheets[0]
        if isinstance(src, io.BytesIO):
            src.seek(0)
        return pd.read_excel(src, sheet_name=sheet, dtype={ID: str})
    return pd.read_csv(src, dtype={ID: str})


def is_v2(raw: pd.DataFrame) -> bool:
    cols = {str(c).strip() for c in raw.columns}
    return len(MARKERS & cols) >= 2


def missing_columns(raw: pd.DataFrame) -> list[str]:
    """Raw columns the model needs that the file lacks (engineered features are rebuilt from these)."""
    _backend_on_path()
    from case3.features import CATEGORICAL, NUMERIC
    return [c for c in [ID, "Aircraft_ID", "Maintenance_Date"] + CATEGORICAL + NUMERIC if c not in raw.columns]


def load_bundle() -> dict:
    _backend_on_path()
    import joblib  # noqa: F401 (imported here so v1 mode never needs it)
    import case3.model  # noqa: F401 (BlendModel must be importable to unpickle)
    return joblib.load(MODEL_PATH)


def load_report() -> dict | None:
    return json.loads(REPORT_PATH.read_text()) if REPORT_PATH.exists() else None


def load_importance() -> pd.Series | None:
    if not IMPORTANCE_PATH.exists():
        return None
    s = pd.read_csv(IMPORTANCE_PATH, index_col=0).iloc[:, 0]
    return s.sort_values(ascending=False)


def band(p: np.ndarray, thr: float) -> np.ndarray:
    """High Risk = the model predicts a defect (p >= threshold); Medium = at least half the threshold."""
    return np.where(p >= thr, "High Risk", np.where(p >= thr / 2, "Medium", "Normal"))


def score(raw: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    _backend_on_path()
    from case3.features import prepare
    df = prepare(raw)
    df[ID] = raw[ID].astype(str).to_numpy()
    p = bundle["model"].predict_proba(df)
    df["Defect_Probability"] = p
    df["Predicted"] = np.where(p >= bundle["threshold"], "Yes", "No")
    df["Band"] = band(p, bundle["threshold"])
    df["Month"] = df["Maintenance_Date"].dt.to_period("M").astype(str)
    if TARGET in df and df[TARGET].isin(["Yes", "No"]).any():
        df["actual"] = (df[TARGET] == "Yes").astype(int)
    df["pred"] = (df["Predicted"] == "Yes").astype(int)
    return df


def has_labels(df: pd.DataFrame) -> bool:
    return "actual" in df


def rate_col(df: pd.DataFrame) -> tuple[str, str]:
    """Which rate to show: real defects when the file has answers, otherwise predicted defects."""
    return ("actual", "Defect rate") if has_labels(df) else ("pred", "Predicted defect rate")


def rate_by(df: pd.DataFrame, col: str) -> pd.DataFrame:
    rc, _ = rate_col(df)
    g = df.groupby(col, observed=True)[rc].agg(["sum", "count"]).rename(columns={"sum": "defects", "count": "jobs"})
    g["rate"] = g["defects"] / g["jobs"]
    return g.reset_index().rename(columns={col: "level"}).sort_values("level")


def monthly(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("Month").agg(jobs=("pred", "size"), predicted=("pred", "sum"))
    g["predicted_rate"] = g["predicted"] / g["jobs"]
    if has_labels(df):
        a = df.groupby("Month")["actual"].sum()
        g["actual"] = a
        g["actual_rate"] = a / g["jobs"]
    return g.reset_index()


def tool_calibration(df: pd.DataFrame) -> pd.DataFrame:
    rc, _ = rate_col(df)
    g = df.groupby("Tool_ID", observed=True).agg(
        jobs=(rc, "size"), defects=(rc, "sum"), median_days=("Days_Since_Tool_Calibration", "median"),
        median_uses=("Tool_Uses_Since_Calibration", "median"))
    g["rate"] = g["defects"] / g["jobs"]
    return g.sort_values("rate", ascending=False)


def calibration_finding(df: pd.DataFrame) -> str:
    """One generated sentence on the tool with the highest rate and how overdue it is compared with the rest."""
    t = tool_calibration(df)
    if t.empty or t["defects"].sum() == 0:
        return "No tool stands out."
    top, rest = t.index[0], t.iloc[1:]
    word = "defects" if has_labels(df) else "predicted defects"
    days = t.loc[top, "median_days"]
    rest_days = df.loc[df["Tool_ID"] != top, "Days_Since_Tool_Calibration"].median()
    s = (f"{top} has the highest rate of {word}: {int(t.loc[top, 'defects'])} of {int(t.loc[top, 'jobs'])} jobs "
         f"({t.loc[top, 'rate']:.0%}, vs {rest['defects'].sum() / max(rest['jobs'].sum(), 1):.0%} for other tools)")
    if pd.notna(days) and pd.notna(rest_days):
        s += f"; median {days:.0f} days since calibration vs {rest_days:.0f} for other tools"
    return s + "."


def aircraft_board(df: pd.DataFrame) -> pd.DataFrame:
    """One row per aircraft: its highest-risk episode, with that episode's readings."""
    worst = df.sort_values("Defect_Probability", ascending=False).drop_duplicates("Aircraft_ID")
    n = df.groupby("Aircraft_ID").agg(episodes=("pred", "size"), flagged=("pred", "sum"))
    out = worst.set_index("Aircraft_ID").join(n).reset_index()
    out["_rank"] = out["Band"].map(BANDS.index)
    return out.sort_values(["_rank", "Defect_Probability"], ascending=[True, False]).drop(columns="_rank")


def inspection_list(df: pd.DataFrame) -> pd.DataFrame:
    cols = {ID: "Record_ID", "Aircraft_ID": "Aircraft", "Engine_ID": "Engine", "Maintenance_Date": "Date",
            "Maintenance_Station": "Station", "Tool_ID": "Tool", "Days_Since_Tool_Calibration": "Days since cal.",
            "Tension_Diff_Pct": "Tension diff %", "Belt_Temperature_C": "Belt temp °C",
            "Belt_Vibration_mm_s": "Vibration mm/s", "Belt_Age_Hours": "Belt age h", "Belt_Batch_ID": "Batch",
            "Defect_Probability": "Defect probability"}
    sel = df[df["Predicted"] == "Yes"].sort_values("Defect_Probability", ascending=False)
    out = sel[[c for c in cols if c in sel]].rename(columns=cols)
    if has_labels(df):
        out["Actual"] = sel[TARGET].to_numpy()
    return out.round({"Tension diff %": 1, "Belt temp °C": 1, "Vibration mm/s": 2, "Belt age h": 0,
                      "Defect probability": 3})


def metrics(df: pd.DataFrame) -> dict | None:
    if not has_labels(df):
        return None
    y, p = df["actual"].to_numpy(), df["pred"].to_numpy()
    tp, fp, fn = int(((y == 1) & (p == 1)).sum()), int(((y == 0) & (p == 1)).sum()), int(((y == 1) & (p == 0)).sum())
    return {"tp": tp, "fp": fp, "fn": fn, "f1": 2 * tp / max(2 * tp + fp + fn, 1),
            "precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1)}


def submission(df: pd.DataFrame) -> tuple[bytes, list[str]]:
    """case_3_predictions.csv bytes for the uploaded IDs, plus the organisers' format checks run on it."""
    _backend_on_path()
    from case3.submission import check_submission
    out = pd.DataFrame({ID: df[ID], TARGET: df["Predicted"]})
    data = out.to_csv(index=False, lineterminator="\n").encode("utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case_3_predictions.csv"
        path.write_bytes(data)
        problems = check_submission(path, df[ID])
    return data, problems
