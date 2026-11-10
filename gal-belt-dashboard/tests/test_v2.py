"""Release-v2 mode: detection, scoring with the saved model, submission export, and the full page.

Uses synthetic v2 rows built here (the competition files are not committed). Needs Backend/output/model.joblib.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src import data as data_mod
from src import v2

from .conftest import ROOT

pytestmark = pytest.mark.skipif(not v2.MODEL_PATH.exists(), reason="trained model not found")

APP = str(ROOT / "app.py")


def synthetic(n=240, seed=0, bad_tool="Tool-07", labels=False) -> pd.DataFrame:
    """v2-shaped rows; `bad_tool` jobs are far overdue for calibration, hot, vibrating and off-tension."""
    rng = np.random.default_rng(seed)
    tools = [f"Tool-0{i}" for i in range(1, 9)]
    d = pd.DataFrame({
        "Record_ID": [f"BR-T-{i:05d}" for i in range(n)],
        "Aircraft_ID": [f"B787-{rng.integers(1, 41):03d}" for _ in range(n)],
        "Engine_ID": [f"ENG-{i % 40 + 1:03d}-L" for i in range(n)],
        "Maintenance_Date": pd.date_range("2025-05-01", periods=n, freq="9h").strftime("%Y-%m-%dT%H:%M"),
        "Maintenance_Station": rng.choice(["Station A", " station b", "STATION C "], n),
        "Technician_ID": [f"TECH-{rng.integers(1, 61):02d}" for _ in range(n)],
        "Tool_ID": rng.choice(tools, n),
        "High_Load_Hours_Last_30_Days": rng.uniform(60, 140, n),
        "Hot_Operation_Days_Last_30_Days": rng.integers(2, 10, n),
        "Peak_Operating_Temperature_C": rng.uniform(80, 95, n),
        "Belt_Supplier": rng.choice(["Supplier A", "Supplier B"], n),
        "Belt_Batch_ID": rng.choice(["A-01", "A-02", "B-01", "B-02"], n),
        "Days_Since_Tool_Calibration": rng.uniform(5, 60, n),
        "Tool_Uses_Since_Calibration": rng.uniform(30, 350, n),
        "Belt_Age_Hours": rng.uniform(200, 2500, n),
        "Cycles_Since_Belt_Install": rng.uniform(30, 450, n),
        "Belt_Target_Tension_N": rng.uniform(548, 552, n),
        "Ambient_Temperature_C": rng.uniform(18, 32, n),
        "Relative_Humidity_Pct": rng.uniform(20, 80, n),
        "Engine_Load_Ratio": rng.uniform(0.5, 0.9, n),
        "Alignment_Offset_mm": rng.uniform(0, 0.8, n),
        "Contamination_Index": rng.uniform(0, 0.3, n),
        "Operating_Hours_Last_30_Days": rng.uniform(250, 400, n),
        "Belt_Temperature_C": rng.uniform(55, 70, n),
        "Belt_Vibration_mm_s": rng.uniform(1.5, 3.0, n),
        "Belt_Slip_Pct": rng.uniform(0.1, 0.8, n),
    })
    d["Belt_Measured_Tension_N"] = d["Belt_Target_Tension_N"] * rng.uniform(0.98, 1.02, n)
    bad = d["Tool_ID"] == bad_tool
    d.loc[bad, ["Days_Since_Tool_Calibration", "Tool_Uses_Since_Calibration", "Belt_Age_Hours",
                "Cycles_Since_Belt_Install", "Belt_Temperature_C", "Belt_Vibration_mm_s", "Belt_Slip_Pct",
                "Hot_Operation_Days_Last_30_Days", "Peak_Operating_Temperature_C"]] = \
        [210, 1600, 5600, 1500, 96, 6.5, 2.5, 20, 108]
    d.loc[bad, "Belt_Measured_Tension_N"] = d.loc[bad, "Belt_Target_Tension_N"] * 1.15
    d.loc[rng.random(n) < 0.03, "Belt_Vibration_mm_s"] = np.nan  # real files have ~3% missing values
    if labels:
        d["Defect_Found"] = np.where(bad, "Yes", "No")
    return d


@pytest.fixture(scope="module")
def bundle():
    return v2.load_bundle()


def test_detection():
    assert v2.is_v2(synthetic())
    assert not v2.is_v2(pd.read_csv(data_mod.DEFAULT_DATA))  # the 30-row sample stays in the original mode


def test_scoring_flags_the_bad_tool(bundle):
    df = v2.score(synthetic(), bundle)
    assert df["Defect_Probability"].between(0, 1).all()
    flagged = df[df["Predicted"] == "Yes"]
    assert len(flagged) and (flagged["Tool_ID"] == "Tool-07").mean() > 0.9
    assert v2.calibration_finding(df).startswith("Tool-07")


def test_finding_follows_the_data(bundle):
    df = v2.score(synthetic(bad_tool="Tool-02", seed=3), bundle)
    finding = v2.calibration_finding(df)
    assert finding.startswith("Tool-02") and "Tool-07" not in finding


def test_submission_export_passes_checks(bundle):
    df = v2.score(synthetic(), bundle)
    data, problems = v2.submission(df)
    assert problems == []
    lines = data.decode().strip().split("\n")
    assert lines[0] == "Record_ID,Defect_Found" and len(lines) == len(df) + 1
    assert {ln.split(",")[1] for ln in lines[1:]} <= {"Yes", "No"}


def test_labelled_file_gets_metrics(bundle):
    df = v2.score(synthetic(labels=True), bundle)
    m = v2.metrics(df)
    assert v2.has_labels(df) and m["recall"] > 0.9


def test_missing_columns_reported():
    assert "Belt_Measured_Tension_N" in v2.missing_columns(synthetic().drop(columns="Belt_Measured_Tension_N"))


def run_app_on(tmp_path: Path, frame: pd.DataFrame, name="v2.csv") -> AppTest:
    path = tmp_path / name
    frame.to_csv(path, index=False)
    original = data_mod.DEFAULT_DATA
    data_mod.DEFAULT_DATA = path
    try:
        at = AppTest.from_file(APP, default_timeout=180)
        at.run()
    finally:
        data_mod.DEFAULT_DATA = original
    return at


def test_app_renders_v2_test_inputs(tmp_path):
    at = run_app_on(tmp_path, synthetic())
    assert not at.exception, at.exception
    banner = next(m.value for m in at.markdown if "FLEET ALERT" in m.value)
    assert "Tool-07" in banner and "predicted to have a belt defect" in banner
    labels = [m.label for m in at.metric]
    assert labels[:2] == ["Screening episodes", "Predicted defects"] and len(labels) == 4
    assert len(at.tabs) == 4
    assert any("passes every format check" in s.value for s in at.success)


def test_app_renders_v2_labelled(tmp_path):
    at = run_app_on(tmp_path, synthetic(labels=True))
    assert not at.exception, at.exception
    assert "Actual defects" in [m.label for m in at.metric]
    assert any("On this file:" in m.value for m in at.markdown)
