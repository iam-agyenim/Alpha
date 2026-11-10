"""Fleet status board: per-aircraft belt status and the fleet alert card."""
import pandas as pd

from src import impact, stats
from src.data import normalise

from .conftest import no_defects, other_tool_faulty
from .test_app import run_app


def fleet(frame: pd.DataFrame) -> pd.DataFrame:
    d = normalise(frame).df
    return impact.fleet_status(d, stats.detect_top_factor(d))


def test_bundled_statuses(df):
    f = impact.fleet_status(df, stats.detect_top_factor(df))
    assert len(f) == f["Aircraft_ID"].nunique() == 30
    assert (f["Status"] == "High Risk").sum() == 11
    assert set(f.loc[f["Status"] == "High Risk", "Tool_ID"]) == {"Tool-05"}
    assert list(f["Status"]) == sorted(f["Status"], key=impact.STATUS_ORDER.index)  # worst first


def test_medium_rules(raw):
    out = no_defects(raw)
    out[["Belt_Condition", "Belt_Temperature", "Belt_Vibration"]] = "Normal"
    out["Tool_Status"] = "Normal"
    out.loc[0, "Belt_Vibration"] = "High"            # one abnormal reading -> Medium
    out.loc[1, ["Belt_Condition", "Belt_Temperature"]] = ["Abnormal", "High"]  # two -> High Risk
    out.loc[2, "Tool_Status"] = "Overdue"            # tool not Normal -> Medium
    f = fleet(out).set_index("Aircraft_ID")
    assert f.loc[raw.loc[0, "Aircraft_ID"], "Status"] == "Medium"
    assert f.loc[raw.loc[1, "Aircraft_ID"], "Status"] == "High Risk"
    assert f.loc[raw.loc[2, "Aircraft_ID"], "Status"] == "Medium"


def test_worst_record_per_aircraft(raw):
    out = raw.copy()
    dup = out[out["Belt_Defect"] == "Yes"].iloc[[0]].copy()
    ok = out[out["Belt_Defect"] == "No"].iloc[[0]].copy()
    ok["Aircraft_ID"] = dup["Aircraft_ID"].values  # same aircraft, one clean and one defective record
    ok["Record_ID"] = "R999"
    f = fleet(pd.concat([out, ok], ignore_index=True))
    row = f[f["Aircraft_ID"] == dup["Aircraft_ID"].iloc[0]]
    assert len(row) == 1 and row["Status"].iloc[0] == "High Risk"


def card(at) -> str:
    return next(m.value for m in at.markdown if "FLEET ALERT" in m.value)


def test_alert_card_bundled():
    at = run_app()
    c = card(at)
    assert "11 B787 aircraft have abnormal belt measurements." in c
    assert "more common when Tool-05" in c


def test_alert_card_follows_data(tmp_path, raw):
    at = run_app(tmp_path, other_tool_faulty(raw))
    c = card(at)
    assert "7 B787 aircraft have abnormal belt measurements." in c
    assert "Tool-02" in c and "Tool-05" not in c
