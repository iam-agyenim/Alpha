"""Turn a workflow run into a PDF report, plain text, work-order CSV and a pre-filled email link.

Email uses a mailto: link, so it opens the user's own email app with the report filled in; nothing is sent by
the server and no email credentials are needed. A mailto link can't carry attachments, so download the PDF and
attach it if needed.
"""
import datetime as dt
from urllib.parse import quote

from fpdf import FPDF

NAVY, BLUE, GREY = (11, 11, 11), (11, 107, 58), (74, 79, 76)   # black, green, grey
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
def run_text(run) -> str:
    o = run.outputs
    m = o.get("model", {})
    c = (o.get("commercial") or {}).get("output") or {}
    orders = (o.get("outputs") or {}).get("work_orders", [])
    lines = [f"B787 belt-health workflow run {run.run_id} ({run.batch_label})", "",
             f"Model: {m.get('predicted_defects', '-')} predicted defects, {m.get('aircraft_high_risk', '-')} aircraft "
             f"High Risk, {m.get('aircraft_medium', '-')} Medium; tool most linked to risk: "
             f"{m.get('tool_most_linked_to_risk', '-')}.", ""]
    if c:
        lines += ["Recommendation: " + c.get("recommendation_to_approver", ""), ""]
    if run.approval:
        lines += [f"Decision: {run.approval['decision']} by {run.approval['approver']} at {run.approval['time'][:16]} UTC", ""]
    if orders:
        lines += ["Work orders:"] + [f"- {w['id']} [{w['priority']}] {w['type']}: {w['target']} - {w['owner']}"
                                     for w in orders]
    lines += ["", "Decision support only; a qualified engineer makes every maintenance decision."]
    return "\n".join(lines)


def work_orders_csv(run) -> str:
    import csv
    import io
    orders = (run.outputs.get("outputs") or {}).get("work_orders", [])
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["id", "type", "target", "priority", "owner", "detail"])
    w.writeheader()
    w.writerows(orders)
    return buf.getvalue()


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
        self.set_draw_color(11, 107, 58)
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


def run_pdf(run) -> bytes:
    o = run.outputs
    pdf = _Report(f"Maintenance workflow report - run {run.run_id}")
    meter = run.meter or {}
    pdf.title_block(f"Batch: {run.batch_label} - started {run.started[:16].replace('T', ' ')} UTC - "
                    f"{meter.get('tokens', 0):,} tokens - ${meter.get('usd', 0):.3f}")
    m, sec = o.get("model", {}), o.get("security_input", {})
    pdf.heading("1. Data and security")
    pdf.para(f"{sec.get('rows_received', '-')} screenings received, {sec.get('rows_valid', '-')} valid, "
             f"{sec.get('rows_quarantined', '-')} quarantined. " + "; ".join(sec.get("issues", [])))
    pdf.heading("2. ML model results")
    pdf.para(f"{m.get('predicted_defects', '-')} predicted defects; {m.get('aircraft_high_risk', '-')} aircraft High Risk, "
             f"{m.get('aircraft_medium', '-')} Medium. Tool most linked to risk: {m.get('tool_most_linked_to_risk', '-')}. "
             f"{m.get('model', '')}")
    q = (o.get("quality") or {}).get("output") or {}
    if q:
        pdf.heading("3. Quality & Safety agent")
        pdf.para(q.get("summary", ""))
        for x in q.get("inspections", []):
            pdf.bullet(f"{x['priority']} {x['aircraft']} {x['engine']}: {x['reason']}")
        for t in q.get("tool_actions", []):
            pdf.bullet(f"{t['tool']}: {t['action']} - {t['reason']}")
    lg = (o.get("logistics") or {}).get("output") or {}
    if lg:
        pdf.heading("4. Logistics agent")
        pdf.para(lg.get("summary", ""))
        for p in lg.get("parts_plan", []):
            pdf.bullet(f"{p['station']}: belts needed {p['belts_needed']}, in stock {p['belts_in_stock']}, "
                       f"to order {p['belts_to_order']}")
        for c in lg.get("calibration_plan", []):
            pdf.bullet(f"{c['tool']}: calibration slot {c['slot']}, loan tool {c['loan_tool']}")
    c = (o.get("commercial") or {}).get("output") or {}
    if c:
        pdf.heading("5. Commercial agent")
        pdf.para(c.get("summary", ""))
        cs = c.get("cost_summary", {})
        pdf.para(f"Plan cost ${cs.get('action_cost_usd', 0):,} vs predicted defect cost at risk "
                 f"${cs.get('predicted_defect_cost_at_risk_usd', 0):,}. {cs.get('note', '')}")
        pdf.para("Recommendation: " + c.get("recommendation_to_approver", ""), bold=True)
    pdf.heading("6. Security output check")
    for k, v in (o.get("security_output") or {}).items():
        pdf.bullet(f"{k}: {v}")
    pdf.heading("7. Decision and work orders")
    if run.approval:
        pdf.para(f"{run.approval['decision']} by {run.approval['approver']} at {run.approval['time'][:16]} UTC. "
                 f"{run.approval.get('comment', '')}", bold=True)
    for w in (o.get("outputs") or {}).get("work_orders", []):
        pdf.bullet(f"{w['id']} [{w['priority']}] {w['type']}: {w['target']} - {w['owner']}. {w['detail']}")
    pdf.ln(2)
    pdf.para("Logistics and commercial figures use planning assumptions. Associations are not proof of cause. "
             "Decision support only; a qualified engineer makes every maintenance decision.", size=9, color=GREY)
    return bytes(pdf.output())
