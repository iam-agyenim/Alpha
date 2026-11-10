from src import model as m
from src.data import normalise

from .conftest import no_defects, other_tool_faulty, sample_rows

FORBIDDEN = {"Belt_Condition", "Belt_Temperature", "Belt_Vibration", "Record_ID", "Aircraft_ID"}

BAD_JOB = dict(Tool_ID="Tool-05", Tool_Status="Needs Calibration", Maintenance_Station="Station A", Month="Jan")
GOOD_JOB = dict(Tool_ID="Tool-01", Tool_Status="Normal", Maintenance_Station="Station C", Month="Mar")


def test_no_leakage_features(df):
    assert not FORBIDDEN & set(m.PRE_JOB_FEATURES)
    for fit in (m.fit_tree(df), m.fit_logistic(df)):
        assert not FORBIDDEN & set(fit["features"])


def test_tree_rule(df):
    t = m.fit_tree(df)
    assert any("Needs Calibration" in r or "Tool-05" in r for r in t["english"])
    assert t["dot"].startswith("digraph")


def test_logistic_and_firth(df):
    lr = m.fit_logistic(df)
    assert lr["fitted"].query("defect == 1")["risk"].min() > 0.5
    f = m.fit_firth(df)
    assert f["converged"]


def test_validation_warns(df):
    v = m.validate_pre_job(df)
    assert v["logistic"]["loo"]["recall"] == 1.0
    assert any("unstable" in w for w in v["logistic"]["warnings"])
    assert any("separation" in w.lower() for w in v["logistic"]["warnings"])


def test_leakage_demo(df):
    assert m.leakage_demo(df)["validation"]["loo"]["auc"] == 1.0


def test_checker(df):
    lr = m.fit_logistic(df)
    bad = m.check_job(df, lr, BAD_JOB)
    good = m.check_job(df, lr, GOOD_JOB)
    assert bad["band"] == "High" and "swap" in bad["recommendation"].lower()
    assert good["band"] == "Low" and "Normal" in good["reason"]
    assert bad["bayes"]["ci_low"] < bad["bayes"]["post_mean"] < bad["bayes"]["ci_high"]


def test_models_on_variants(raw):
    for variant in (other_tool_faulty(raw), sample_rows(raw), no_defects(raw)):
        d = normalise(variant).df
        m.fit_tree(d)
        lr = m.fit_logistic(d) if d["defect"].nunique() > 1 else None
        m.validate_pre_job(d)
        m.leakage_demo(d)
        if lr:
            m.check_job(d, lr, BAD_JOB)
