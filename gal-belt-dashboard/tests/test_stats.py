import math

import pandas as pd
import pytest

from src import impact, stats
from src.data import load, month_order, normalise

from .conftest import no_defects, other_tool_faulty, sample_rows


def test_counts(df):
    assert len(df) == 30
    assert df["defect"].sum() == 11


def test_top_factor(df):
    top = stats.detect_top_factor(df)
    assert top["factor"] == "Tool_ID" and top["level"] == "Tool-05"
    assert top["rate"] == 1.0 and top["rate_rest"] == 0.0
    assert {"factor": "Tool_Status", "level": "Needs Calibration"} in top["confounded_with"]


def test_fisher_tool05(df):
    fl = stats.fisher_level_tests(df)
    p = fl[(fl.factor == "Tool_ID") & (fl.level == "Tool-05")]["p_fisher"].iloc[0]
    assert p == pytest.approx(1.83e-8, abs=1e-9)


def test_station_chi_square(df):
    r = stats.chi_square_factor(df, "Maintenance_Station")
    assert r["p_chi2"] == pytest.approx(0.37, abs=0.01)
    assert r["cramers_v"] == pytest.approx(0.26, abs=0.01)
    assert r["min_expected"] < 5 and r["exact_method"]  # small counts flagged


def test_monthly(df):
    top = stats.detect_top_factor(df)
    m = stats.monthly_summary(df, top)
    assert m["month"].tolist() == ["Jan", "Feb", "Mar"]
    assert m["defects"].tolist() == [3, 4, 4]
    assert m["suspect_jobs"].tolist() == [3, 4, 4]


def test_cochran_armitage(df):
    assert stats.cochran_armitage(df)["p"] == pytest.approx(0.64, abs=0.02)


def test_p_chart(df):
    pc = stats.p_chart(df)
    assert pc["centre"] == pytest.approx(0.367, abs=0.005)
    assert pc["table"]["ucl"].iloc[0] == pytest.approx(0.824, abs=0.005)
    assert pc["out_months"] == []


def test_station_vanishes_within_tool(df):
    s = stats.stratify(df, "Maintenance_Station", "Tool_ID")
    assert not s["effect_survives"]
    assert (s["verdicts"]["rate_spread"] == 0).all()


def test_bayes(df):
    b = stats.bayes_rates(df, "Tool_Status").set_index("level")
    nc = b.loc["Needs Calibration"]
    assert nc["post_mean"] == pytest.approx(12 / 13)
    assert nc["ci_low"] < nc["post_mean"] < nc["ci_high"]
    assert nc["p_higher_than_rest"] > 0.99


def test_pareto(df):
    p = stats.pareto(df)
    assert p.iloc[0]["level"] == "Tool-05"
    assert p["cum_pct"].iloc[-1] == pytest.approx(100)


def test_calibration_gate(df):
    g = impact.calibration_gate(df)
    assert g["defects_avoided"] == 11
    assert g["reduction_pct"] == pytest.approx(100)


def test_alert_text(df):
    text = stats.alert_text(df, stats.detect_top_factor(df))
    assert "11 of 30 jobs (37%)" in text and "Tool-05" in text and "0 of 19 with other tools" in text


def test_stratified_conclusion(df):
    top = stats.detect_top_factor(df)
    text = stats.stratified_conclusion(df, top)
    assert "no effect" in text and "Tool-05" in text


def test_confounding_line(df):
    line = stats.confounding_line(stats.detect_top_factor(df))
    assert "Tool-05" in line and "Needs Calibration" in line and "11 jobs" in line


def test_affected_aircraft(df):
    a = impact.affected_aircraft(df, stats.detect_top_factor(df))
    assert len(a) == 11 and (a["Tool"] == "Tool-05").all()


# ---------------------------------------------------------------- robustness

def test_normalisation_variants(raw):
    messy = raw.rename(columns={"Tool_Status": "tool status", "Belt_Defect": "DEFECT", "Maintenance_Station": "Station"})
    messy["DEFECT"] = messy["DEFECT"].map({"Yes": "Y", "No": "false"})
    messy["tool status"] = messy["tool status"].replace({"Needs Calibration": "Overdue"})
    messy["Month"] = messy["Month"].map({"Jan": "2026-01-05", "Feb": "February", "Mar": "3"})
    res = normalise(messy)
    assert res.ok
    assert res.df["defect"].sum() == 11
    assert set(res.df["Tool_Status"]) == {"Normal", "Needs Calibration"}
    assert month_order(res.df["Month"].unique()) == ["Jan", "Feb", "Mar"]


def test_missing_columns(raw):
    res = normalise(raw.drop(columns=["Tool_ID", "Month"]))
    assert not res.ok and set(res.missing) == {"Tool_ID", "Month"}


def test_other_tool_detected(raw):
    res = normalise(other_tool_faulty(raw))
    top = stats.detect_top_factor(res.df)
    assert top["level"] == "Tool-02"
    assert "Tool-02" in stats.alert_text(res.df, top)


def test_no_defects(raw):
    d = normalise(no_defects(raw)).df
    assert stats.detect_top_factor(d) is None
    assert impact.calibration_gate(d)["reduction_pct"] == 0
    stats.factor_ranking(d)
    stats.p_chart(d)
    stats.cochran_armitage(d)
    assert stats.confounding_line(None) is None
    for f in stats.factors_present(d):
        stats.chi_square_factor(d, f)
        stats.bayes_rates(d, f)


def test_sample_runs(raw):
    d = normalise(sample_rows(raw)).df
    top = stats.detect_top_factor(d)
    stats.factor_ranking(d)
    stats.stratify(d, "Maintenance_Station", "Tool_ID")
    stats.stratified_conclusion(d, top)
    stats.mantel_haenszel(d, top, "Maintenance_Station")
