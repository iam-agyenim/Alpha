"""Cleaning and features: messy spellings are unified, and every feature uses only its own row."""
import numpy as np
import pandas as pd

from case3.features import CATEGORICAL, ENGINEERED, NUMERIC, prepare, target


def frame(n=4):
    return pd.DataFrame({
        "Record_ID": [f"R{i}" for i in range(n)], "Aircraft_ID": ["B787-001"] * n, "Engine_ID": ["ENG-001-L"] * n,
        "Maintenance_Date": ["2024-07-01T10:00"] * n,
        "Maintenance_Station": ["Station A", " station a ", "STATION A", "station b"][:n],
        "Technician_ID": ["TECH-01", "tech-01 ", "TECH-02", "tech-03"][:n],
        "Tool_ID": ["Tool-05", "tool-05 ", " TOOL-05", "Tool-01"][:n],
        "Belt_Supplier": ["Supplier B", "supplier b ", "SUPPLIER B", "Supplier A"][:n],
        "Belt_Batch_ID": ["B-07", "b-07 ", "B-07", "a-01"][:n],
        **{c: np.linspace(1, 2, n) for c in NUMERIC},
        "Belt_Target_Tension_N": [550.0] * n, "Belt_Measured_Tension_N": [605.0, 495.0, np.nan, 550.0][:n],
        "Defect_Found": ["Yes", "No", " yes", "No"][:n],
    })


def test_spelling_variants_unified():
    d = prepare(frame())
    assert set(d["Maintenance_Station"][:3]) == {"Station A"}
    assert set(d["Tool_ID"][:3]) == {"Tool-05"}
    assert set(d["Technician_ID"][:2]) == {"TECH-01"}
    assert set(d["Belt_Supplier"][:3]) == {"Supplier B"}
    assert set(d["Belt_Batch_ID"][:3]) == {"B-07"}


def test_target_tolerates_case_and_spaces():
    assert list(target(prepare(frame()))) == [1, 0, 1, 0]


def test_tension_difference():
    d = prepare(frame())
    assert np.isclose(d.loc[0, "Tension_Diff_Pct"], 10.0) and np.isclose(d.loc[1, "Tension_Diff_Pct"], -10.0)
    assert np.isclose(d.loc[1, "Abs_Tension_Diff_Pct"], 10.0)
    assert np.isnan(d.loc[2, "Tension_Diff_Pct"])  # missing measurement stays missing, not invented


def test_features_use_only_their_own_row():
    """Rules: build each prediction from that row only. Preparing rows one at a time must match batch output."""
    f = frame()
    batch = prepare(f)[CATEGORICAL + NUMERIC + ENGINEERED]
    single = pd.concat([prepare(f.iloc[[i]]) for i in range(len(f))])[CATEGORICAL + NUMERIC + ENGINEERED]
    pd.testing.assert_frame_equal(batch.reset_index(drop=True), single.reset_index(drop=True), check_dtype=False)
