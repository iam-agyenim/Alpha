"""Turn agent reports into a PDF, plain text and a pre-filled email link (for the Share buttons).

Email uses a mailto: link, so it opens the user's own email app with the report filled in; nothing is sent by
the server and no email credentials are needed. A mailto link can't carry attachments, so download the PDF and
attach it if needed.
"""
import datetime as dt
from urllib.parse import quote

from fpdf import FPDF

NAVY, BLUE, GREY = (27, 42, 90), (34, 80, 156), (82, 81, 78)
MAILTO_BODY_LIMIT = 1800          # keep mailto URLs within what email apps accept

# Built-in PDF fonts are Latin-1 only; map the few symbols the agents use.
_REPLACE = {"≤": "<=", "≥": ">=", "–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "×": "x",
            "→": "->", "•": "-", "…": "...", "✓": "OK", "⚠": "!", " ": " ", " ": " "}


def _latin1(text) -> str:
    text = str(text)
    for k, v in _REPLACE.items():
        text = text.replace(k, v)
    return text.replace("**", "").encode("latin-1", "replace").decode("latin-1")


# --------------------------------------------------------------------------- plain text (email body, copy)
def specialist_text(r) -> str:
    out = r.output if isinstance(r.output, dict) else {}
    lines = [f"{r.agent}: belt-health report", "", out.get("headline", ""), ""]
    for i, f in enumerate(out.get("findings", []), 1):
        lines += [f"{i}. [{f['severity'].upper()}] {f['finding']}", f"   Evidence: {f['evidence']}"]
    if out.get("recommended_actions"):
        lines += ["", "Recommended actions:"] + [f"- {a}" for a in out["recommended_actions"]]
    if out.get("open_questions"):
        lines += ["", "Open questions:"] + [f"- {q}" for q in out["open_questions"]]
    lines += ["", f"Confidence: {out.get('confidence', '-')}. Number check: "
              + ("passed" if not r.ungrounded and not r.error else f"review ({', '.join(r.ungrounded) or r.error})"),
              "Decision support only; a qualified engineer makes every maintenance decision."]
    return "\n".join(lines)


def briefing_text(result) -> str:
    plan = result.lead.output if isinstance(result.lead.output, dict) else {}
    lines = ["B787 belt-health team briefing", "", plan.get("executive_summary", ""), "", "Priority actions:"]
    for a in sorted(plan.get("priority_actions", []), key=lambda a: a["rank"]):
        lines += [f"{a['rank']}. [{a['urgency']}] {a['action']} | Target: {a['target']} | Owner: {a['owner']}",
                  f"   Evidence: {a['evidence']}"]
    if plan.get("risks_and_caveats"):
        lines += ["", "Risks and caveats:"] + [f"- {x}" for x in plan["risks_and_caveats"]]
    lines += ["", "Decision support only; a qualified engineer makes every maintenance decision."]
    return "\n".join(lines)


def mailto_link(to: str, subject: str, body: str) -> str:
    if len(body) > MAILTO_BODY_LIMIT:
        body = body[:MAILTO_BODY_LIMIT] + "\n\n[Shortened: see the attached PDF for the full report.]"
    return f"mailto:{quote(to.strip(), safe='@')}?subject={quote(subject)}&body={quote(body)}"


# --------------------------------------------------------------------------- PDF
class _Report(FPDF):
    def __init__(self, title: str):
        super().__init__(format="A4")
        self.report_title = _latin1(title)
        self.set_auto_page_break(True, margin=16)
        self.set_margins(16, 16, 16)
        self.add_page()

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*BLUE)
        self.cell(0, 6, "CASE 3 - B787 FLEET BELT HEALTH", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(168, 135, 58)
        self.set_line_width(0.6)
        self.line(16, self.get_y(), 40, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 6, _latin1(f"Generated {dt.datetime.now():%d %b %Y %H:%M} by the AI agent team - decision "
                                f"support only - page {self.page_no()}"), align="C")

    def title_block(self, subtitle: str):
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(*NAVY)
        self.multi_cell(0, 9, self.report_title, new_x="LMARGIN", new_y="NEXT", align="L")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*GREY)
        self.multi_cell(0, 5, _latin1(subtitle), new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def heading(self, text: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*NAVY)
        self.multi_cell(0, 6, _latin1(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def para(self, text: str, size=10.5, bold=False, color=(11, 11, 11), indent=0):
        self.set_font("Helvetica", "B" if bold else "", size)
        self.set_text_color(*color)
        self.set_x(16 + indent)
        self.multi_cell(0, 5.2, _latin1(text), new_x="LMARGIN", new_y="NEXT", align="L")

    def bullet(self, text: str, indent=0):
        self.para(f"-  {text}", indent=indent)


def specialist_pdf(r) -> bytes:
    out = r.output if isinstance(r.output, dict) else {}
    pdf = _Report(f"{r.agent}: belt-health report")
    pdf.title_block(f"{len(r.tool_log)} tool calls - confidence: {out.get('confidence', '-')} - number check: "
                    + ("passed" if not r.ungrounded and not r.error else "review needed"))
    pdf.para(out.get("headline", ""), size=12, bold=True)
    pdf.heading("Findings")
    for i, f in enumerate(out.get("findings", []), 1):
        pdf.para(f"{i}. [{f['severity'].upper()}] {f['finding']}", bold=True)
        pdf.para(f"Evidence: {f['evidence']}", size=9.5, color=GREY, indent=5)
        pdf.ln(1)
    if out.get("recommended_actions"):
        pdf.heading("Recommended actions")
        for a in out["recommended_actions"]:
            pdf.bullet(a)
    if out.get("open_questions"):
        pdf.heading("Open questions")
        for q in out["open_questions"]:
            pdf.bullet(q)
    pdf.heading("Data used")
    pdf.para(" · ".join(f"{t['tool']}({', '.join(f'{k}={v}' for k, v in t['args'].items())})" for t in r.tool_log)
             or "none", size=9, color=GREY)
    pdf.ln(2)
    pdf.para("Associations are not proof of cause. Decision support only; a qualified engineer makes every "
             "maintenance decision.", size=9, color=GREY)
    return bytes(pdf.output())


def briefing_pdf(result) -> bytes:
    plan = result.lead.output if isinstance(result.lead.output, dict) else {}
    pdf = _Report("Team briefing: action plan")
    pdf.title_block(f"{len(result.specialists)} specialists + lead planner - {result.meter.total_tokens:,} tokens - "
                    f"${result.meter.total_usd:.3f}")
    pdf.para(plan.get("executive_summary", ""), size=11.5)
    pdf.heading("Priority actions")
    for a in sorted(plan.get("priority_actions", []), key=lambda a: a["rank"]):
        pdf.para(f"{a['rank']}. [{a['urgency']}] {a['action']}", bold=True)
        pdf.para(f"Target: {a['target']}  |  Owner: {a['owner']}  |  Raised by: {', '.join(a['raised_by'])}",
                 size=9.5, indent=5)
        pdf.para(f"Evidence: {a['evidence']}", size=9.5, color=GREY, indent=5)
        pdf.ln(1)
    if plan.get("cross_checks"):
        pdf.heading("How the agents checked each other")
        for c in plan["cross_checks"]:
            pdf.bullet(f"{c['topic']} ({', '.join(c['agents'])}): {c['outcome']}")
    if plan.get("risks_and_caveats"):
        pdf.heading("Risks and caveats")
        for x in plan["risks_and_caveats"]:
            pdf.bullet(x)
    if plan.get("cost_of_inaction"):
        pdf.heading("Cost of doing nothing")
        pdf.para(plan["cost_of_inaction"])
    for r in result.specialists:
        o = r.output if isinstance(r.output, dict) else {}
        pdf.heading(f"Specialist: {r.agent}")
        pdf.para(o.get("headline", r.error or ""), bold=True)
        for f in o.get("findings", []):
            pdf.bullet(f"[{f['severity'].upper()}] {f['finding']}")
    return bytes(pdf.output())
