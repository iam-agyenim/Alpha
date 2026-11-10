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
