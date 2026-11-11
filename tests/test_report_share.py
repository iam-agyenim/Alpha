"""Offline tests for the Share buttons: PDF, text and email link."""
import sys
from pathlib import Path
from types import SimpleNamespace as N

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
import report_share as rs  # noqa: E402

from belt_defect.agents.cost import CostMeter  # noqa: E402

SPECIALIST = N(agent="Tool & calibration analyst", seconds=12.0, error=None, ungrounded=[],
               tool_log=[{"tool": "tool_status", "args": {}, "result": {}}],
               output={"headline": "Pull Tool-03 first", "confidence": "high",
                       "findings": [{"finding": "Tool-03 is overdue", "severity": "high",
                                     "evidence": "179 days, tension +6.4% (normal ≤ 9.7%) – 32.9% predicted"}],
                       "recommended_actions": ["Calibrate Tool-03"], "open_questions": []})
LEAD = N(agent="Lead planner", seconds=20.0, error=None, ungrounded=[], tool_log=[],
         output={"executive_summary": "Inspect 9 High Risk aircraft; pull Tool-03.",
                 "priority_actions": [{"rank": 1, "action": "Pull Tool-03", "target": "Tool-03", "urgency": "Today",
                                       "owner": "Tool crib / calibration", "evidence": "179 days",
                                       "raised_by": ["Tool & calibration analyst"]}],
                 "cross_checks": [], "risks_and_caveats": ["Synthetic data"], "cost_of_inaction": "n/a"})


def test_specialist_pdf_and_text():
    pdf = rs.specialist_pdf(SPECIALIST)
    assert pdf[:4] == b"%PDF" and len(pdf) > 1000
    text = rs.specialist_text(SPECIALIST)
    assert "Tool-03 is overdue" in text and "Number check: passed" in text


def test_briefing_pdf():
    result = N(specialists=[SPECIALIST], lead=LEAD, meter=CostMeter())
    assert rs.briefing_pdf(result)[:4] == b"%PDF"
    assert "Pull Tool-03" in rs.briefing_text(result)


def test_mailto_link_is_encoded_and_capped():
    link = rs.mailto_link("tool.crib@example.com", "Tool report", "line\n" * 2000)
    assert link.startswith("mailto:tool.crib@example.com?subject=Tool%20report&body=")
    assert "Shortened" in link and len(link) < 4000


def test_unicode_is_pdf_safe():
    assert rs._latin1("≤ 9.7% – ok → done") == "<= 9.7% - ok -> done"
