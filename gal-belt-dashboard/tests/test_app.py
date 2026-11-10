"""Smoke tests: the whole app renders without exceptions on the bundled file and on modified files."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src import data as data_mod

from .conftest import ROOT, no_defects, other_tool_faulty, sample_rows

APP = str(ROOT / "app.py")


def run_app(tmp_path: Path | None = None, frame=None, present=False) -> AppTest:
    if frame is not None:
        path = tmp_path / "variant.csv"
        frame.to_csv(path, index=False)
        original = data_mod.DEFAULT_DATA
        data_mod.DEFAULT_DATA = path
    try:
        at = AppTest.from_file(APP, default_timeout=120)
        at.run()
        if present:
            at.toggle[0].set_value(True).run()
    finally:
        if frame is not None:
            data_mod.DEFAULT_DATA = original
    return at


def test_app_bundled():
    at = run_app()
    assert not at.exception, at.exception
    assert "Tool-05" in alert(at) and "11 of 30 jobs" in alert(at)


def test_app_presentation_mode():
    at = run_app(present=True)
    assert not at.exception, at.exception


def alert(at: AppTest) -> str:
    return next(m.value for m in at.markdown if "ALERT" in m.value)


def test_app_sample_rows(tmp_path, raw):
    at = run_app(tmp_path, sample_rows(raw))
    assert not at.exception, at.exception
    assert "of 20 jobs" in alert(at)
    assert not [t for t in all_text(at) if "30 jobs" in t or "of 30" in t]  # no leftover full-data counts


def test_app_other_tool(tmp_path, raw):
    at = run_app(tmp_path, other_tool_faulty(raw))
    assert not at.exception, at.exception
    assert "Tool-02" in alert(at) and "Tool-05" not in alert(at)


def test_app_no_defects(tmp_path, raw):
    at = run_app(tmp_path, no_defects(raw))
    assert not at.exception, at.exception
    assert "0 of 30 jobs" in alert(at)


def test_app_missing_columns(tmp_path, raw):
    at = run_app(tmp_path, raw.drop(columns=["Tool_ID"]))
    assert not at.exception
    assert any("Tool_ID" in e.value for e in at.error)


def all_text(at: AppTest) -> list[str]:
    """Every piece of visible text the app writes (not table cells or chart data)."""
    out = []
    for kind in ("title", "header", "subheader", "markdown", "caption", "warning", "error", "info", "success"):
        out += [e.value for e in getattr(at, kind)]
    out += [f"{m.label} {m.value}" for m in at.metric]
    return out


def test_faulty_tool_swap_changes_every_text(tmp_path, raw):
    """If Tool-02 is the faulty tool, nothing on screen may still name Tool-05 (no hardcoded findings)."""
    at = run_app(tmp_path, other_tool_faulty(raw))
    assert not at.exception, at.exception
    texts = all_text(at)
    leaks = [t for t in texts if "Tool-05" in t]
    assert not leaks, leaks

    # Banner
    assert "Tool-02" in alert(at) and "7 of 7 jobs" in alert(at)
    # KPIs
    labels = {m.label: m.value for m in at.metric}
    assert labels["Defect rate with Tool-02"] == "100%"
    assert labels["Defect rate without Tool-02"] == "0%"
    assert labels["Aircraft requiring follow-up"] == "7"
    # Stratification conclusion
    assert any("no effect" in t and "Tool-02" in t for t in at.markdown.values)
    # Decision-tree rule (learned from data)
    rules = [t for t in at.markdown.values if t.startswith("- IF")]
    assert rules and any("Tool-02" in r or "Needs Calibration" in r for r in rules)
    assert all("Tool-05" not in r for r in rules)
    # Affected-aircraft list
    aff = next(d.value for d in at.dataframe if "Priority" in d.value.columns)
    assert set(aff["Tool"]) == {"Tool-02"} and len(aff) == 7
    # Risk checker defaults to the new suspect
    assert at.selectbox(key="job_Tool_ID").value == "Tool-02"


def test_bundled_text_mentions_tool05(tmp_path):
    """Sanity check for the test above: on the GAL data the same text does name Tool-05."""
    at = run_app()
    assert any("Tool-05" in t for t in all_text(at))
