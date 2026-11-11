"""Offline tests for workflow outputs: PDF report, work-order CSV, text and email link."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
import report_share as rs  # noqa: E402

from belt_defect import config  # noqa: E402
from belt_defect.agents import workflow as W  # noqa: E402

SAMPLE = config.OUTPUT_DIR / "workflow_runs" / "sample_run.json"


def _approved_run():
    run = W.WorkflowRun.from_json(SAMPLE.read_text())
    return W.approve_run(run, "Approved", "Test Manager", "ok")


def test_sample_run_is_waiting_for_approval():
    run = W.WorkflowRun.from_json(SAMPLE.read_text())
    assert run.status["approval"] == "running" and len(run.events) > 20


def test_run_pdf_csv_and_text():
    run = _approved_run()
    assert rs.run_pdf(run)[:4] == b"%PDF"
    csv = rs.work_orders_csv(run)
    assert csv.startswith("id,type,target,priority,owner,detail") and "Belt inspection" in csv
    assert "Approved by Test Manager" in rs.run_text(run)


def test_mailto_link_is_encoded_and_capped():
    link = rs.mailto_link("tool.crib@example.com", "Work orders", "line\n" * 2000)
    assert link.startswith("mailto:tool.crib@example.com?subject=Work%20orders&body=")
    assert "Shortened" in link and len(link) < 4000


def test_unicode_is_pdf_safe():
    assert rs._latin1("≤ 9.7% – ok → done") == "<= 9.7% - ok -> done"
