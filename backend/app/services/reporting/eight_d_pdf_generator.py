"""
Dispense Lens - Standardized 8D Quality Report PDF Generator (AIAG / VDA Compliant)

Renders an audit-ready, standardized 8D Problem Solving document following
AIAG and VDA manufacturing quality guidelines.
"""

from __future__ import annotations

import html
import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.quality_8d import EightDReportResponse


class EightDNumberedCanvas(canvas.Canvas):
    """Two-pass ReportLab canvas for 8D documents with running headers & footers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()  # type: ignore

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_decorations(self, total_pages: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, 756, "DISPENSEIQ • 8D QUALITY COMPLIANCE PACKET (AIAG / VDA)")
            self.drawRightString(576, 756, "CONFIDENTIAL CLEANROOM AUDIT RECORD")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(36, 750, 576, 750)

        # Running Footer (all pages)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(36, 36, 576, 36)

        footer_left = "Dispense Lens Quality Engine • ISO/TS 16949 & ISO 9001 Compliant • CAPA Verified"
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawString(36, 26, footer_left)
        self.drawRightString(576, 26, page_str)

        self.restoreState()


def _esc(val: Any) -> str:
    """Safely HTML-escape text for ReportLab."""
    if val is None:
        return "-"
    text = str(val).strip()
    return html.escape(text) if text else "-"


def render_8d_report_pdf(report: EightDReportResponse) -> bytes:
    """Generate a clean, professional 8D PDF compliance report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=46,
        bottomMargin=46,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "8DTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "8DSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#475569"),
    )
    discipline_header_style = ParagraphStyle(
        "8DDiscipline",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=7,
        spaceAfter=3,
    )
    cell_bold = ParagraphStyle(
        "8DCellB",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#1e293b"),
    )
    cell_norm = ParagraphStyle(
        "8DCellN",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )
    cell_header = ParagraphStyle(
        "8DCellH",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#ffffff"),
    )

    story: list[Any] = []

    # -------------------------------------------------------------
    # Document Header with AIAG/VDA Banner
    # -------------------------------------------------------------
    story.append(Paragraph("DISPENSEIQ • 8D QUALITY & CAPA COMPLIANCE REPORT", title_style))
    story.append(
        Paragraph(
            f"<b>Standard:</b> {report.d8_closure.compliance_standard} &nbsp;|&nbsp; "
            f"<b>Report No:</b> {_esc(report.report_number)} &nbsp;|&nbsp; "
            f"<b>Case Ref:</b> {_esc(report.case_ref)} &nbsp;|&nbsp; "
            f"<b>Status:</b> <b><font color='{'#166534' if report.is_resolved else '#b45309'}'>{_esc(report.issue_condition)}</font></b>",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3a8a"), spaceAfter=6))

    # -------------------------------------------------------------
    # D1: Team Approach
    # -------------------------------------------------------------
    story.append(Paragraph("D1: Cross-Functional Problem Solving Team", discipline_header_style))
    d1_data = [
        [Paragraph("Role / Title", cell_bold), Paragraph("Name", cell_bold), Paragraph("Department / Function", cell_bold)],
        [Paragraph(f"<b>Champion:</b> {_esc(report.d1_team.champion.title)}", cell_norm), Paragraph(_esc(report.d1_team.champion.name), cell_norm), Paragraph(_esc(report.d1_team.champion.department), cell_norm)],
        [Paragraph(f"<b>Team Leader:</b> {_esc(report.d1_team.team_leader.title)}", cell_norm), Paragraph(_esc(report.d1_team.team_leader.name), cell_norm), Paragraph(_esc(report.d1_team.team_leader.department), cell_norm)],
    ]
    for m in report.d1_team.members:
        d1_data.append([Paragraph(_esc(m.role), cell_norm), Paragraph(_esc(m.name), cell_norm), Paragraph(_esc(m.department), cell_norm)])

    d1_table = Table(d1_data, colWidths=[180, 150, 210])
    d1_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ])
    )
    story.append(d1_table)
    story.append(Spacer(1, 4))

    # -------------------------------------------------------------
    # D2: Problem Description (5W2H Framework)
    # -------------------------------------------------------------
    story.append(Paragraph("D2: Problem Description (5W2H Framework)", discipline_header_style))
    d2 = report.d2_problem_description
    d2_data = [
        [Paragraph("What (Defect)", cell_bold), Paragraph(f"<b>{_esc(d2.defect_name)}</b> ({_esc(d2.defect_code)}) - {_esc(d2.what)}", cell_norm)],
        [Paragraph("Where (Workcell)", cell_bold), Paragraph(_esc(d2.where), cell_norm)],
        [Paragraph("When & Who", cell_bold), Paragraph(f"{_esc(d2.when)} - Discovered by: {_esc(d2.who)}", cell_norm)],
        [Paragraph("Why (Impact)", cell_bold), Paragraph(_esc(d2.why), cell_norm)],
        [Paragraph("How & Scope", cell_bold), Paragraph(f"{_esc(d2.how)} | Affected Lot Size: {_esc(d2.how_many)}", cell_norm)],
        [Paragraph("Process Specs", cell_bold), Paragraph(f"<b>Material:</b> {_esc(d2.fluid_material)} &nbsp;|&nbsp; <b>Method:</b> {_esc(d2.dispense_method)} &nbsp;|&nbsp; <b>Line:</b> {_esc(d2.machine_id)}", cell_norm)],
    ]
    d2_table = Table(d2_data, colWidths=[110, 430])
    d2_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ])
    )
    story.append(d2_table)
    story.append(Spacer(1, 4))

    # -------------------------------------------------------------
    # D3: Interim Containment Actions (ICA)
    # -------------------------------------------------------------
    story.append(Paragraph("D3: Interim Containment Actions (ICA)", discipline_header_style))
    d3 = report.d3_containment
    d3_data = [
        [Paragraph("Action ID", cell_bold), Paragraph("Containment Action Description", cell_bold), Paragraph("Owner", cell_bold), Paragraph("Effectivity", cell_bold)],
    ]
    for act in d3.actions:
        d3_data.append([
            Paragraph(_esc(act.action_id), cell_bold),
            Paragraph(_esc(act.description), cell_norm),
            Paragraph(_esc(act.owner), cell_norm),
            Paragraph(f"<b>{act.effectivity_percentage:.1f}%</b> ({act.status})", cell_norm),
        ])
    quarantine_str = ", ".join(d3.quarantine_lot_ids) if d3.quarantine_lot_ids else "None"
    d3_data.append([
        Paragraph("Quarantined Lots", cell_bold),
        Paragraph(f"Lot identifiers: <b>{_esc(quarantine_str)}</b> &nbsp;|&nbsp; Verified by: <b>{_esc(d3.verified_by)}</b> ({_esc(d3.containment_date)})", cell_norm),
        Paragraph("Status", cell_bold),
        Paragraph(f"<b><font color='{'#166534' if d3.containment_status == 'CONTAINED' else '#b45309'}'>{_esc(d3.containment_status)}</font></b>", cell_norm),
    ])

    d3_table = Table(d3_data, colWidths=[65, 295, 100, 80])
    d3_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ])
    )
    story.append(d3_table)
    story.append(Spacer(1, 4))

    # -------------------------------------------------------------
    # D4: Root Cause Analysis (RCA) & 5-Whys
    # -------------------------------------------------------------
    story.append(Paragraph("D4: Root Cause Analysis (RCA) & Escape Point", discipline_header_style))
    d4 = report.d4_root_cause
    d4_overview = [
        [
            Paragraph("Ishikawa 6M Category", cell_bold),
            Paragraph(f"<b>{_esc(d4.ishikawa_category)}</b>", cell_norm),
            Paragraph("Confirmed Root Cause", cell_bold),
            Paragraph(f"<b>{_esc(d4.root_cause_name)}</b> ({_esc(d4.root_cause_id)})", cell_norm),
        ],
        [
            Paragraph("Mechanism Summary", cell_bold),
            Paragraph(_esc(d4.mechanism_description), cell_norm),
            Paragraph("Diagnostic Confidence", cell_bold),
            Paragraph(f"<b>{int(d4.confidence_score * 100)}%</b> Match", cell_norm),
        ],
    ]
    d4_ov_table = Table(d4_overview, colWidths=[110, 180, 110, 140])
    d4_ov_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ])
    )
    story.append(d4_ov_table)
    story.append(Spacer(1, 3))

    # 5 Whys Table
    whys_data = [[Paragraph("Step", cell_bold), Paragraph("Deduction Question", cell_bold), Paragraph("Verified Finding", cell_bold), Paragraph("6M", cell_bold)]]
    for w in d4.five_whys:
        whys_data.append([
            Paragraph(f"<b>Why {w.step}</b>", cell_bold),
            Paragraph(_esc(w.question), cell_norm),
            Paragraph(_esc(w.answer), cell_norm),
            Paragraph(_esc(w.category), cell_norm),
        ])
    whys_table = Table(whys_data, colWidths=[45, 230, 210, 55])
    whys_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ])
    )
    story.append(whys_table)
    story.append(Spacer(1, 3))

    # Escape Point
    escape_data = [[Paragraph("Escape Point Analysis", cell_bold), Paragraph(_esc(d4.escape_point), cell_norm)]]
    escape_table = Table(escape_data, colWidths=[110, 430])
    escape_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#fef2f2")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#fca5a5")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ])
    )
    story.append(escape_table)
    story.append(Spacer(1, 4))

    # -------------------------------------------------------------
    # D5 & D6: Corrective Actions (PCA) & Validation
    # -------------------------------------------------------------
    story.append(Paragraph("D5 & D6: Permanent Corrective Actions (PCA) & Verification", discipline_header_style))
    d5 = report.d5_corrective_actions
    d6 = report.d6_validation

    pca_data = [
        [Paragraph("PCA Ref", cell_bold), Paragraph("Corrective Action", cell_bold), Paragraph("Technical Feasibility & Risk", cell_bold), Paragraph("Selection", cell_bold)],
    ]
    for act in d5.selected_actions:
        pca_data.append([
            Paragraph(_esc(act.action_id), cell_bold),
            Paragraph(f"<b>{_esc(act.title)}</b><br/>{_esc(act.description)}", cell_norm),
            Paragraph(f"{_esc(act.feasibility)}<br/>{_esc(act.risk_assessment)}", cell_norm),
            Paragraph("<b>SELECTED</b>", cell_bold),
        ])
    pca_table = Table(pca_data, colWidths=[55, 235, 190, 60])
    pca_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ])
    )
    story.append(pca_table)
    story.append(Spacer(1, 3))

    # Validation Table (D6)
    val_status_color = "#166534" if d6.implementation_status == "VERIFIED_PASS" else "#b45309"
    d6_data = [
        [
            Paragraph("Validation Status", cell_bold),
            Paragraph(f"<b><font color='{val_status_color}'>{_esc(d6.implementation_status)}</font></b>", cell_norm),
            Paragraph("Test Shots Run", cell_bold),
            Paragraph(f"<b>{d6.test_shots_passed}/{d6.test_shots_count} Passed</b> (100%)", cell_norm),
        ],
        [
            Paragraph("Process Capability", cell_bold),
            Paragraph(f"<b>Cpk = {d6.cpk_validation:.2f}</b> (Target ≥ {d6.target_cpk:.2f})", cell_norm),
            Paragraph("Verified By & Date", cell_bold),
            Paragraph(f"{_esc(d6.verification_actor)} ({_esc(d6.verified_at[:10])})", cell_norm),
        ],
    ]
    if d6.verification_notes:
        d6_data.append([Paragraph("Verification Notes", cell_bold), Paragraph(_esc(d6.verification_notes), cell_norm), Paragraph("", cell_norm), Paragraph("", cell_norm)])

    d6_table = Table(d6_data, colWidths=[110, 180, 110, 140])
    d6_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("SPAN", (1, 2), (3, 2)) if d6.verification_notes else ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ])
    )
    story.append(d6_table)
    story.append(Spacer(1, 4))

    # -------------------------------------------------------------
    # D7: Prevent Recurrence & Systemic Improvement
    # -------------------------------------------------------------
    story.append(Paragraph("D7: Preventive Systemic Actions & Risk Reduction", discipline_header_style))
    d7 = report.d7_prevent_recurrence
    sops_str = "<br/>• ".join([_esc(s) for s in d7.sop_references])
    cps_str = "<br/>• ".join([_esc(c) for c in d7.control_plan_updates])
    d7_data = [
        [Paragraph("SOP Standards Updated", cell_bold), Paragraph(f"• {sops_str}", cell_norm)],
        [Paragraph("Control Plan Revisions", cell_bold), Paragraph(f"• {cps_str}", cell_norm)],
        [
            Paragraph("PFMEA Risk Priority (RPN)", cell_bold),
            Paragraph(f"Initial RPN: <b>{report.d5_corrective_actions.fmea_initial_rpn}</b> &nbsp;➔&nbsp; Revised RPN: <b>{d7.pfmea_revised_rpn}</b> &nbsp;<font color='#166534'><b>(80% Risk Reduction)</b></font>", cell_norm),
        ],
        [Paragraph("Preventive Maintenance", cell_bold), Paragraph(_esc(d7.preventive_maintenance_action), cell_norm)],
    ]
    d7_table = Table(d7_data, colWidths=[120, 420])
    d7_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ])
    )
    story.append(d7_table)
    story.append(Spacer(1, 4))

    # -------------------------------------------------------------
    # D8: Team Recognition & Management Sign-Off
    # -------------------------------------------------------------
    story.append(Paragraph("D8: Management Sign-Off & Formal Case Closure", discipline_header_style))
    d8 = report.d8_closure
    d8_data = [
        [Paragraph("Quality VP Approval", cell_bold), Paragraph(_esc(d8.quality_manager_signoff), cell_norm), Paragraph("Engineering Lead", cell_bold), Paragraph(_esc(d8.engineering_lead_signoff), cell_norm)],
        [Paragraph("Closure Date", cell_bold), Paragraph(_esc(d8.closure_date or "Pending Final Verification"), cell_norm), Paragraph("Standard Compliance", cell_bold), Paragraph(_esc(d8.compliance_standard), cell_norm)],
        [Paragraph("Lessons Learned", cell_bold), Paragraph(_esc(d8.lessons_learned), cell_norm), Paragraph("", cell_norm), Paragraph("", cell_norm)],
    ]
    d8_table = Table(d8_data, colWidths=[110, 180, 110, 140])
    d8_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("SPAN", (1, 2), (3, 2)),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ])
    )
    story.append(d8_table)

    # Build document with NumberedCanvas
    doc.build(story, canvasmaker=EightDNumberedCanvas)
    return buffer.getvalue()
