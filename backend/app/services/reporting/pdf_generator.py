"""Dispense Lens - Deterministic Downloadable PDF Case Report Generator.

Renders a complete, professional, competition-demo-ready PDF document from an
already-accepted, immutable CaseReportResponse read model.

Requirements (DLK-M3-023):
- Renders strictly from the accepted CaseReportResponse model.
- Zero direct database queries or secondary data paths.
- Zero diagnostic recalculation.
- Deterministic section layout and content ordering.
- Multi-page support with running headers, footers, and "Page X of Y" numbering.
- Automatic text-wrapping in table cells to prevent overflow or clipping.
- Clear neutral display ("None recorded") for empty history sections.
"""

from __future__ import annotations

import html
import io
import math
from datetime import datetime
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

from app.schemas.case import CaseReportResponse
from app.schemas.diagnosis import CauseConclusion
from app.services.reporting.quality_assessment import (
    calculate_dispensing_quality,
    get_learning_insight_report,
)


class NumberedCanvas(canvas.Canvas):
    """Two-pass ReportLab canvas that dynamically computes total page count and
    draws consistent running headers, footers, and 'Page X of Y' numbering.
    """

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
            self._draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_page_decorations(self, page_count: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))  # slate-500

        # Running Header (on all pages)
        self.drawString(36, 756, "Dispense Lens Diagnostic Automation System - Case Report")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))  # slate-300
        self.setLineWidth(0.5)
        self.line(36, 750, 576, 750)

        # Running Footer (on all pages)
        self.line(36, 48, 576, 48)
        self.drawString(36, 36, "Generated from persisted diagnostic records")
        page_text = f"Page {self._pageNumber} of {page_count}"  # type: ignore
        self.drawRightString(576, 36, page_text)

        self.restoreState()


def _escape(val: Any) -> str:
    """Safely format and HTML-escape any value for ReportLab Paragraphs."""
    if val is None:
        return "-"
    if isinstance(val, datetime):
        return html.escape(val.strftime("%Y-%m-%d %H:%M:%S UTC"))
    if hasattr(val, "value"):
        return html.escape(str(val.value))
    text = str(val).strip()
    return html.escape(text) if text else "-"


def _truncate_str(val: Any, max_len: int = 200) -> str:
    """Safely format, HTML-escape, and truncate any value with a visible notice if exceeded."""
    if val is None:
        return "-"
    if isinstance(val, datetime):
        return html.escape(val.strftime("%Y-%m-%d %H:%M:%S UTC"))
    if hasattr(val, "value"):
        s = str(val.value).strip()
    else:
        s = str(val).strip()
    if len(s) > max_len:
        truncated = s[:max_len]
        return f"{html.escape(truncated)} <font color='#b45309'>[truncated (exceeds {max_len} chars)]</font>"
    return html.escape(s) if s else "-"


def _is_finite_number(val: Any) -> bool:
    """Exception-safe check whether val is a finite int or float."""
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    try:
        f = float(val)
        return math.isfinite(f)
    except (OverflowError, ValueError, TypeError):
        return False


def _fmt_num(val: Any) -> str:
    """Format numeric values cleanly, '-' if None, or 'unavailable' if invalid scalar."""
    if val is None:
        return "-"
    if not _is_finite_number(val):
        return "unavailable"
    if isinstance(val, float):
        return f"{val:.4f}".rstrip("0").rstrip(".") if abs(val) < 10 else f"{val:.2f}"
    s = str(val)
    if len(s) > 200:
        return f"{s[:200]} <font color='#b45309'>[truncated (exceeds 200 chars)]</font>"
    return s


def _fmt_bool(val: Any) -> str:
    """Format boolean value cleanly, '-' if None, or 'unavailable' if invalid scalar."""
    if val is None:
        return "-"
    if isinstance(val, bool):
        return "True" if val else "False"
    return "unavailable"


KNOWN_LIMIT_KEYS = frozenset({
    # Process limits
    "min_coverage_ratio",
    "max_coverage_ratio",
    "max_overflow_ratio",
    "max_size_cv",
    "min_presence_ratio",
    "min_circularity",
    "min_solidity",
    "min_convexity",
    "max_aspect_ratio",
    "min_aspect_ratio",
    "max_bubble_count",
    "max_void_ratio",
    # Reference limits
    "min_reference_ratio",
    "max_reference_ratio",
    "tolerance_ratio",
    "min_circularity_ratio",
    "min_solidity_ratio",
    # Profile/calibration limits
    "target_area_px",
    "tolerance_pct",
    "target_diameter_mm",
    "tolerance_pct_diameter",
})

ALLOWED_INSPECTION_STATUSES = frozenset({"DETECTED", "MISSING", "UNASSESSED"})


def render_case_report_pdf(report: CaseReportResponse) -> bytes:
    """Render a deterministic PDF document from an accepted CaseReportResponse.

    Args:
        report: Pinned CaseReportResponse read model from DLK-M3-022.

    Returns:
        bytes: Complete, parseable PDF binary data.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),  # slate-900
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569"),  # slate-600
    )
    section_heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1e3a8a"),  # blue-900
        spaceBefore=10,
        spaceAfter=4,
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1e293b"),  # slate-800
    )
    cell_normal = ParagraphStyle(
        "CellNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),  # slate-700
    )
    cell_header = ParagraphStyle(
        "CellHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0f172a"),  # slate-900
    )
    empty_notice_style = ParagraphStyle(
        "EmptyNotice",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748b"),  # slate-500
        leftIndent=8,
    )
    cell_small_bold = ParagraphStyle(
        "CellSmallBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#1e293b"),
    )
    cell_small_normal = ParagraphStyle(
        "CellSmallNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#334155"),
    )
    cell_trans = ParagraphStyle(
        "CellTrans",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor("#334155"),
    )

    story: list[Any] = []

    # ---------------------------------------------------------
    # Document Header (NSW Automation Challenge Branding)
    # ---------------------------------------------------------
    nsw_badge_style = ParagraphStyle(
        "NSWBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#4338ca"),  # indigo-700
        spaceAfter=2,
    )
    story.append(Paragraph("<b>AI HORIZON SOLUTION CHALLENGE 2026 &bull; NSW AUTOMATION</b>", nsw_badge_style))
    story.append(Paragraph("AI Dispensing Defect Detective &mdash; Troubleshooting Report", title_style))
    story.append(
        Paragraph(
            "<b>Tagline:</b> <i>&ldquo;Helping Manufacturers Identify Dispensing Problems Faster with AI&rdquo;</i> &nbsp;|&nbsp; "
            "Dispense Lens Diagnostic Case Report",
            subtitle_style,
        )
    )
    story.append(
        Paragraph(
            f"Case Identifier: <b>{_escape(report.case_id)}</b> &nbsp;|&nbsp; "
            f"Report Revision: <b>{_escape(report.current_revision)}</b> &nbsp;|&nbsp; "
            f"Case Created: <b>{_escape(report.created_at)}</b>",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3a8a"), spaceAfter=10))

    # ---------------------------------------------------------
    # 1. Case Identity & Process Context
    # ---------------------------------------------------------
    story.append(Paragraph("1. Case Identity & Process Context", section_heading_style))

    condition_str = _escape(report.issue_condition)
    condition_color = "#166534" if condition_str == "RESOLVED" else "#991b1b" if condition_str == "RECURRED" else "#b45309"

    overview_data = [
        [
            Paragraph("Case ID", cell_bold),
            Paragraph(_escape(report.case_id), cell_normal),
            Paragraph("Current Revision", cell_bold),
            Paragraph(_escape(report.current_revision), cell_normal),
        ],
        [
            Paragraph("Defect Category", cell_bold),
            Paragraph(_escape(report.defect_code), cell_normal),
            Paragraph("Issue Condition", cell_bold),
            Paragraph(f"<b><font color='{condition_color}'>{condition_str}</font></b>", cell_normal),
        ],
        [
            Paragraph("Defect Name", cell_bold),
            Paragraph(_escape(report.defect_name), cell_normal),
            Paragraph("Created Timestamp", cell_bold),
            Paragraph(_escape(report.created_at), cell_normal),
        ],
        [
            Paragraph("Material", cell_bold),
            Paragraph(_escape(report.material), cell_normal),
            Paragraph("Method", cell_bold),
            Paragraph(_escape(report.method), cell_normal),
        ],
        [
            Paragraph("Problem Description", cell_bold),
            Paragraph(_escape(report.description), cell_normal),
            Paragraph("Machine Context", cell_bold),
            Paragraph(_escape(report.machine_context if report.machine_context else "None specified"), cell_normal),
        ],
    ]

    overview_table = Table(overview_data, colWidths=[100, 170, 100, 170])
    overview_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(overview_table)
    story.append(Spacer(1, 8))

    # ---------------------------------------------------------
    # Dispensing Quality Assessment
    # ---------------------------------------------------------
    quality = calculate_dispensing_quality(report.defect_code, report.defect_name)
    story.append(
        Paragraph(
            f"Dispensing Quality Assessment &nbsp;&mdash;&nbsp; "
            f"<b>Overall Quality Score: {quality.overall_score} / 100</b>",
            section_heading_style,
        )
    )

    quality_rows = [
        [
            Paragraph("Quality Metric", cell_header),
            Paragraph("Rating", cell_header),
            Paragraph("Score", cell_header),
            Paragraph("Status Assessment", cell_header),
            Paragraph("Engineering Details", cell_header),
        ],
        [
            Paragraph(quality.shape.name, cell_bold),
            Paragraph(f"{quality.shape.star_display} ({quality.shape.stars}/5)", cell_normal),
            Paragraph(f"{quality.shape.score}%", cell_normal),
            Paragraph(quality.shape.label, cell_bold),
            Paragraph(quality.shape.description, cell_normal),
        ],
        [
            Paragraph(quality.size.name, cell_bold),
            Paragraph(f"{quality.size.star_display} ({quality.size.stars}/5)", cell_normal),
            Paragraph(f"{quality.size.score}%", cell_normal),
            Paragraph(quality.size.label, cell_bold),
            Paragraph(quality.size.description, cell_normal),
        ],
        [
            Paragraph(quality.position.name, cell_bold),
            Paragraph(f"{quality.position.star_display} ({quality.position.stars}/5)", cell_normal),
            Paragraph(f"{quality.position.score}%", cell_normal),
            Paragraph(quality.position.label, cell_bold),
            Paragraph(quality.position.description, cell_normal),
        ],
        [
            Paragraph(quality.defect_risk.name, cell_bold),
            Paragraph(f"{quality.defect_risk.star_display} ({quality.defect_risk.stars}/5)", cell_normal),
            Paragraph(f"{quality.defect_risk.score}%", cell_normal),
            Paragraph(quality.defect_risk.label, cell_bold),
            Paragraph(quality.defect_risk.description, cell_normal),
        ],
    ]
    quality_table = Table(quality_rows, colWidths=[105, 80, 45, 95, 215])
    quality_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(quality_table)
    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            f"<b>Quality Assessment Rationale:</b> {_escape(quality.summary)}",
            cell_normal,
        )
    )
    story.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # 2. Current Outcome Summary
    # ---------------------------------------------------------
    story.append(Paragraph("2. Current Outcome Summary", section_heading_style))
    summary = report.outcome_summary
    confirmed_str = ", ".join(summary.confirmed_causes) if summary.confirmed_causes else "None confirmed"
    resolved_display = "YES (Resolved)" if summary.is_resolved else "NO (Unresolved / In Progress)"
    resolved_color = "#166534" if summary.is_resolved else "#b45309"

    summary_data = [
        [
            Paragraph("Current Condition", cell_bold),
            Paragraph(f"<b>{_escape(summary.issue_condition)}</b>", cell_normal),
            Paragraph("Revision Basis", cell_bold),
            Paragraph(f"Revision {_escape(summary.current_revision)}", cell_normal),
        ],
        [
            Paragraph("Confirmed Root Causes", cell_bold),
            Paragraph(f"<b>{_escape(confirmed_str)}</b>", cell_normal),
            Paragraph("Is Resolved", cell_bold),
            Paragraph(f"<b><font color='{resolved_color}'>{resolved_display}</font></b>", cell_normal),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[110, 160, 110, 160])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # 3. Current Diagnosis Snapshot
    # ---------------------------------------------------------
    diag = report.current_diagnosis
    rev_num = diag.analysis_revision.revision_number if diag.analysis_revision else report.current_revision
    story.append(
        Paragraph(
            f"3. Current Diagnosis Snapshot (Analysis Revision {rev_num})",
            section_heading_style,
        )
    )

    # Diagnostic Explanation
    explanation_text = diag.explanation.strip() if diag.explanation else ""
    if explanation_text:
        story.append(
            Paragraph(
                f"<b>Diagnostic Explanation:</b> {_escape(explanation_text)}",
                cell_normal,
            )
        )
    else:
        story.append(Paragraph("<b>Diagnostic Explanation:</b> None recorded.", cell_normal))
    story.append(Spacer(1, 6))

    if diag.ranked_causes:
        diag_headers = [
            Paragraph("#", cell_header),
            Paragraph("Cause ID", cell_header),
            Paragraph("Cause Name", cell_header),
            Paragraph("Score", cell_header),
            Paragraph("Conclusion", cell_header),
            Paragraph("Status", cell_header),
        ]
        diag_rows = [diag_headers]
        for idx, cause in enumerate(diag.ranked_causes, start=1):
            is_conf = (
                getattr(cause, "conclusion", None) in (CauseConclusion.CONFIRMED, "CONFIRMED", "confirmed")
                or cause.cause_id in report.outcome_summary.confirmed_causes
            )
            conf_badge = "<b><font color='#166534'>CONFIRMED</font></b>" if is_conf else "Candidate"
            diag_rows.append(
                [
                    Paragraph(str(idx), cell_normal),
                    Paragraph(_escape(cause.cause_id), cell_bold if is_conf else cell_normal),
                    Paragraph(
                        _escape(getattr(cause, "cause_name", getattr(cause, "name", ""))),
                        cell_bold if is_conf else cell_normal,
                    ),
                    Paragraph(f"{cause.score:.1f}", cell_normal),
                    Paragraph(_escape(cause.conclusion), cell_normal),
                    Paragraph(conf_badge, cell_normal),
                ]
            )
        diag_table = Table(diag_rows, colWidths=[25, 115, 160, 50, 110, 80])
        diag_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(diag_table)
        story.append(Spacer(1, 6))

        # Evaluated evidence per candidate cause
        for cause in diag.ranked_causes:
            ev_items: list[tuple[str, Any]] = []
            for ev in getattr(cause, "supporting_evidence", []):
                ev_items.append(("SUPPORTS", ev))
            for ev in getattr(cause, "contradicting_evidence", []):
                ev_items.append(("CONTRADICTS", ev))
            for ev in getattr(cause, "neutral_evidence", []):
                ev_items.append(("NEUTRAL", ev))

            c_name = getattr(cause, "cause_name", getattr(cause, "name", cause.cause_id))
            story.append(
                Paragraph(
                    f"<b>Evaluated Evidence - {_escape(c_name)}</b> (<code>{_escape(cause.cause_id)}</code>):",
                    cell_bold,
                )
            )

            if ev_items:
                ev_headers = [
                    Paragraph("Relation", cell_header),
                    Paragraph("Strength", cell_header),
                    Paragraph("Source", cell_header),
                    Paragraph("Score", cell_header),
                    Paragraph("Observation / Explanation Details", cell_header),
                ]
                ev_rows = [ev_headers]
                for rel_label, ev in ev_items:
                    rel_color = (
                        "#166534"
                        if rel_label == "SUPPORTS"
                        else "#991b1b"
                        if rel_label == "CONTRADICTS"
                        else "#475569"
                    )
                    rel_display = f"<b><font color='{rel_color}'>{_escape(rel_label)}</font></b>"
                    sc_contrib = getattr(ev, "score_contribution", 0.0)
                    score_display = f"{sc_contrib:+.1f}" if sc_contrib is not None else "0.0"
                    ev_src = getattr(ev, "source", "USER")
                    ev_strength = getattr(ev, "strength", "MODERATE")
                    ev_expl = getattr(ev, "explanation", "")
                    obs_id = getattr(ev, "observation_id", "")

                    details_text = _escape(ev_expl) if ev_expl else "-"
                    if obs_id:
                        details_text += f" &nbsp;[obs: <code>{_escape(obs_id)}</code>]"

                    ev_rows.append(
                        [
                            Paragraph(rel_display, cell_normal),
                            Paragraph(_escape(ev_strength), cell_normal),
                            Paragraph(_escape(ev_src), cell_normal),
                            Paragraph(score_display, cell_normal),
                            Paragraph(details_text, cell_normal),
                        ]
                    )
                ev_table = Table(ev_rows, colWidths=[70, 55, 95, 45, 275])
                ev_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                story.append(ev_table)
            else:
                story.append(Paragraph("No evaluated evidence recorded for this cause.", empty_notice_style))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("No ranked causes recorded in this analysis snapshot.", empty_notice_style))
        story.append(Paragraph("<b>Evaluated Diagnostic Evidence:</b> None recorded.", cell_normal))

    story.append(Spacer(1, 6))

    # Recommended Next Question & Check
    if diag.next_question:
        nq = diag.next_question
        opts_str = f" [Options: {', '.join(_escape(o) for o in nq.options)}]" if getattr(nq, "options", None) else ""
        purpose_str = f" - <i>{_escape(nq.purpose)}</i>" if getattr(nq, "purpose", None) else ""
        story.append(
            Paragraph(
                f"<b>Recommended Next Question:</b> [{_escape(nq.question_id)}] {_escape(nq.text)}{opts_str}{purpose_str}",
                cell_normal,
            )
        )
    else:
        story.append(Paragraph("<b>Recommended Next Question:</b> None recorded.", cell_normal))

    if diag.next_check:
        nc = diag.next_check
        proc = getattr(nc, "procedure", "") or getattr(nc, "description", "")
        proc_str = f" - {_escape(proc)}" if proc else ""
        story.append(
            Paragraph(
                f"<b>Recommended Next Troubleshooting Check:</b> [{_escape(nc.check_id)}] {_escape(nc.name)}{proc_str}",
                cell_normal,
            )
        )
    else:
        story.append(Paragraph("<b>Recommended Next Troubleshooting Check:</b> None recorded.", cell_normal))

    story.append(Spacer(1, 8))

    # ---------------------------------------------------------
    # AI Learning Database Insight
    # ---------------------------------------------------------
    insight = get_learning_insight_report(report.defect_code, report.defect_name)
    story.append(
        Paragraph(
            "AI Learning Database Insight",
            section_heading_style,
        )
    )
    insight_content = (
        f"<b>AI Learning Insight:</b> &ldquo;{_escape(insight.insight_text)}&rdquo;<br/>"
        f"<b>Historical Verified Resolution:</b> <font color='#166534'>{_escape(insight.successful_solution)}</font>"
    )
    insight_table = Table([[Paragraph(insight_content, cell_normal)]], colWidths=[540])
    insight_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f3ff")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#a78bfa")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(insight_table)
    story.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # 4. Technician Question-Answer History
    # ---------------------------------------------------------
    story.append(
        Paragraph(
            f"4. Technician Question-Answer History - Question Answers ({len(report.question_answers)})",
            section_heading_style,
        )
    )
    if report.question_answers:
        qa_headers = [
            Paragraph("#", cell_header),
            Paragraph("Question ID", cell_header),
            Paragraph("Answer Value / Text", cell_header),
            Paragraph("Source", cell_header),
            Paragraph("Rev", cell_header),
            Paragraph("Timestamp", cell_header),
        ]
        qa_rows = [qa_headers]
        for idx, qa in enumerate(report.question_answers, start=1):
            ans_display = _escape(qa.answer_value)
            if qa.answer_text and qa.answer_text != qa.answer_value:
                ans_display += f" ({_escape(qa.answer_text)})"
            qa_rows.append(
                [
                    Paragraph(str(idx), cell_normal),
                    Paragraph(_escape(qa.question_id), cell_bold),
                    Paragraph(ans_display, cell_normal),
                    Paragraph(_escape(qa.source), cell_normal),
                    Paragraph(_escape(qa.resulting_revision_number), cell_normal),
                    Paragraph(_escape(qa.answered_at), cell_normal),
                ]
            )
        qa_table = Table(qa_rows, colWidths=[25, 80, 160, 65, 35, 175])
        qa_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(qa_table)
    else:
        story.append(Paragraph("None recorded.", empty_notice_style))

    story.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # 5. Troubleshooting-Check History
    # ---------------------------------------------------------
    story.append(
        Paragraph(
            f"5. Troubleshooting-Check History - Troubleshooting Checks ({len(report.check_results)})",
            section_heading_style,
        )
    )
    if report.check_results:
        cr_headers = [
            Paragraph("#", cell_header),
            Paragraph("Check ID", cell_header),
            Paragraph("Execution", cell_header),
            Paragraph("Finding / Outcome", cell_header),
            Paragraph("Rev", cell_header),
            Paragraph("Timestamp", cell_header),
        ]
        cr_rows = [cr_headers]
        for idx, cr in enumerate(report.check_results, start=1):
            finding_text = f"<b>{_escape(cr.finding)}</b>"
            if cr.outcome:
                finding_text += f": {_escape(cr.outcome)}"
            if cr.finding_details:
                finding_text += f" ({_escape(cr.finding_details)})"
            cr_rows.append(
                [
                    Paragraph(str(idx), cell_normal),
                    Paragraph(_escape(cr.check_id), cell_bold),
                    Paragraph(_escape(cr.execution_status), cell_normal),
                    Paragraph(finding_text, cell_normal),
                    Paragraph(_escape(cr.resulting_revision_number), cell_normal),
                    Paragraph(_escape(cr.checked_at), cell_normal),
                ]
            )
        cr_table = Table(cr_rows, colWidths=[25, 80, 70, 160, 35, 170])
        cr_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(cr_table)
    else:
        story.append(Paragraph("None recorded.", empty_notice_style))

    story.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # 6. Cause-Confirmation History
    # ---------------------------------------------------------
    story.append(
        Paragraph(
            f"6. Cause-Confirmation History - Cause Confirmations ({len(report.cause_confirmations)})",
            section_heading_style,
        )
    )
    if report.cause_confirmations:
        conf_headers = [
            Paragraph("#", cell_header),
            Paragraph("Cause ID", cell_header),
            Paragraph("Confirmed By", cell_header),
            Paragraph("Notes / Details", cell_header),
            Paragraph("Rev", cell_header),
            Paragraph("Timestamp", cell_header),
        ]
        conf_rows = [conf_headers]
        for idx, conf in enumerate(report.cause_confirmations, start=1):
            conf_rows.append(
                [
                    Paragraph(str(idx), cell_normal),
                    Paragraph(_escape(conf.cause_id), cell_bold),
                    Paragraph(_escape(conf.confirmed_by), cell_normal),
                    Paragraph(_escape(conf.notes), cell_normal),
                    Paragraph(_escape(conf.resulting_revision_number), cell_normal),
                    Paragraph(_escape(conf.confirmed_at), cell_normal),
                ]
            )
        conf_table = Table(conf_rows, colWidths=[25, 115, 85, 120, 35, 160])
        conf_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(conf_table)
    else:
        story.append(Paragraph("None recorded.", empty_notice_style))

    story.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # 7. Issue Lifecycle History
    # ---------------------------------------------------------
    story.append(
        Paragraph(
            f"7. Issue Lifecycle History - Lifecycle Events ({len(report.lifecycle_events)})",
            section_heading_style,
        )
    )
    if report.lifecycle_events:
        lc_headers = [
            Paragraph("#", cell_header),
            Paragraph("Event Type", cell_header),
            Paragraph("Condition Transition", cell_header),
            Paragraph("Rev", cell_header),
            Paragraph("Actor", cell_header),
            Paragraph("Details / Verification", cell_header),
            Paragraph("Timestamp", cell_header),
        ]
        lc_rows = [lc_headers]
        for idx, lc in enumerate(report.lifecycle_events, start=1):
            transition_text = f"{_escape(lc.prior_issue_condition)} &rarr;<br/>{_escape(lc.resulting_issue_condition)}"
            details_text = _escape(lc.details)
            if lc.verification_passed is not None:
                v_res = "PASSED" if lc.verification_passed else "FAILED"
                details_text = f"[{v_res}] {details_text}"
            lc_rows.append(
                [
                    Paragraph(str(idx), cell_small_normal),
                    Paragraph(_escape(lc.event_type), cell_small_bold),
                    Paragraph(transition_text, cell_trans),
                    Paragraph(_escape(lc.resulting_revision_number), cell_small_normal),
                    Paragraph(_escape(lc.actor), cell_small_normal),
                    Paragraph(details_text, cell_small_normal),
                    Paragraph(_escape(lc.created_at), cell_small_normal),
                ]
            )
        lc_table = Table(lc_rows, colWidths=[18, 108, 132, 28, 60, 88, 106])
        lc_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(lc_table)
    else:
        story.append(Paragraph("None recorded.", empty_notice_style))

    # ---------------------------------------------------------
    # 8. Image Inspection Evidence
    # ---------------------------------------------------------
    story.append(Spacer(1, 10))
    image_obs_list = getattr(report, "image_observations", None) or []
    story.append(
        Paragraph(
            f"8. Image Inspection Evidence ({len(image_obs_list)})",
            section_heading_style,
        )
    )

    if not image_obs_list:
        story.append(
            Paragraph(
                "No image inspection evidence recorded for this case revision.",
                empty_notice_style,
            )
        )
    else:
        # Notice regarding automated observations
        story.append(
            Paragraph(
                "<i>Notice: Image findings represent automated visual observations and inferences, not confirmed root causes. "
                "Absence of image findings does not imply inspection passed or coverage was complete.</i>",
                cell_small_normal,
            )
        )
        story.append(Spacer(1, 4))

        max_obs = 20
        if len(image_obs_list) > max_obs:
            story.append(
                Paragraph(
                    f"<b>Display Notice:</b> Display bounded to first {max_obs} observations "
                    f"({len(image_obs_list) - max_obs} omitted). Omission does not imply unlisted observations passed.",
                    empty_notice_style,
                )
            )
            story.append(Spacer(1, 4))

        displayed_obs = image_obs_list[:max_obs]

        for obs_idx, obs in enumerate(displayed_obs, start=1):
            obs_meta = obs.metadata if isinstance(obs.metadata, dict) else {}
            raw_scope = obs_meta.get("region_evidence_scope")
            if raw_scope == "comparison_group":
                scope_desc = (
                    "comparison_group (Group comparison finding: listed regions are eligible "
                    "comparison participants evaluated for variation, not individually confirmed failures.)"
                )
            elif raw_scope == "individual_regions":
                scope_desc = "individual_regions (Individual region defect findings)"
            else:
                scope_desc = "Not recorded or unknown"

            # Affected sites: bound to 20, chunk across split-safe rows, report omitted count
            max_affected = 20
            raw_affected = obs_meta.get("affected_roi_ids")
            affected_list: list[str] = []
            if isinstance(raw_affected, list):
                for item in raw_affected:
                    if isinstance(item, (str, int, float)):
                        affected_list.append(_truncate_str(str(item), max_len=200))
                    else:
                        affected_list.append("unavailable")
            elif obs_meta.get("roi_id") is not None:
                single_rid = obs_meta.get("roi_id")
                if isinstance(single_rid, (str, int, float)):
                    affected_list.append(_truncate_str(str(single_rid), max_len=200))
                else:
                    affected_list.append("unavailable")

            total_affected = len(affected_list)
            displayed_affected = affected_list[:max_affected]
            omitted_affected = total_affected - len(displayed_affected)
            affected_chunks = [
                displayed_affected[i : i + 4]
                for i in range(0, len(displayed_affected), 4)
            ]

            # Applied limits: allowlist known names, validate finite scalar values, chunk
            raw_limits = obs_meta.get("applied_limits")
            limit_items: list[str] = []
            if isinstance(raw_limits, dict) and raw_limits:
                for k, v in raw_limits.items():
                    if not isinstance(k, str) or k not in KNOWN_LIMIT_KEYS:
                        continue
                    if v is None:
                        v_str = "-"
                    elif isinstance(v, bool):
                        v_str = "True" if v else "False"
                    elif _is_finite_number(v):
                        v_str = _fmt_num(v)
                    else:
                        v_str = "unavailable"
                    limit_items.append(f"{_escape(k)}: {v_str}")

            if not limit_items:
                limits_rows = [
                    Paragraph(
                        "<b>Applied Limits (configuration snapshot; not an assertion of failure for all limits):</b> None recorded or not specified",
                        cell_small_normal,
                    )
                ]
            else:
                limits_chunks = [
                    limit_items[i : i + 3]
                    for i in range(0, len(limit_items), 3)
                ]
                limits_rows = []
                for l_idx, lchunk in enumerate(limits_chunks):
                    prefix = (
                        "<b>Applied Limits (configuration snapshot; not an assertion of failure for all limits):</b> "
                        if l_idx == 0
                        else ""
                    )
                    limits_rows.append(Paragraph(prefix + ", ".join(lchunk), cell_small_normal))

            # Split-safe summary table for the observation
            obs_val_desc = f"{_truncate_str(obs.observation_type, max_len=200)} = {_truncate_str(obs.value, max_len=200)}"
            if obs.original_text and obs.original_text != obs.value:
                obs_val_desc += f" ({_truncate_str(obs.original_text, max_len=200)})"

            obs_summary_rows = [
                [
                    Paragraph(
                        f"<b>Observation #{obs_idx}:</b> {obs_val_desc}",
                        cell_bold,
                    ),
                    Paragraph(
                        f"<b>Source:</b> {_truncate_str(obs.source, max_len=200)} | <b>Statement:</b> {_truncate_str(obs.statement_type, max_len=200)} | <b>First-Seen Rev:</b> {_truncate_str(obs.first_seen_revision, max_len=200)}",
                        cell_small_normal,
                    ),
                ],
                [
                    Paragraph(f"<b>Scope:</b> {html.escape(scope_desc)}", cell_small_normal),
                    Paragraph("", cell_small_normal),
                ],
            ]
            span_commands: list[tuple[Any, ...]] = [
                ("SPAN", (0, 1), (1, 1)),
            ]
            r_idx = 2

            if total_affected == 0:
                obs_summary_rows.append([
                    Paragraph("<b>Affected Sites:</b> None recorded", cell_small_normal),
                    Paragraph("", cell_small_normal),
                ])
                span_commands.append(("SPAN", (0, r_idx), (1, r_idx)))
                r_idx += 1
            else:
                for a_idx, achunk in enumerate(affected_chunks):
                    prefix = "<b>Affected Sites:</b> " if a_idx == 0 else ""
                    obs_summary_rows.append([
                        Paragraph(prefix + ", ".join(achunk), cell_small_normal),
                        Paragraph("", cell_small_normal),
                    ])
                    span_commands.append(("SPAN", (0, r_idx), (1, r_idx)))
                    r_idx += 1
                if omitted_affected > 0:
                    obs_summary_rows.append([
                        Paragraph(
                            f"<i>Display Notice: Showing first {len(displayed_affected)} of {total_affected} affected sites "
                            f"({omitted_affected} omitted. Omission does not imply unlisted sites passed.)</i>",
                            empty_notice_style,
                        ),
                        Paragraph("", cell_small_normal),
                    ])
                    span_commands.append(("SPAN", (0, r_idx), (1, r_idx)))
                    r_idx += 1

            for lrow in limits_rows:
                obs_summary_rows.append([
                    lrow,
                    Paragraph("", cell_small_normal),
                ])
                span_commands.append(("SPAN", (0, r_idx), (1, r_idx)))
                r_idx += 1

            obs_summary_table = Table(obs_summary_rows, colWidths=[270, 270])
            obs_summary_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ]
                    + span_commands
                )
            )
            story.append(obs_summary_table)
            story.append(Spacer(1, 3))

            # Region evidence
            region_ev = obs_meta.get("region_evidence")
            if not isinstance(region_ev, list) or len(region_ev) == 0:
                story.append(
                    Paragraph(
                        "Detailed per-region evidence was not recorded for this observation.",
                        empty_notice_style,
                    )
                )
                story.append(Spacer(1, 6))
                continue

            max_regions = 50
            if len(region_ev) > max_regions:
                story.append(
                    Paragraph(
                        f"<b>Display Notice:</b> Showing first {max_regions} of {len(region_ev)} region entries "
                        f"({len(region_ev) - max_regions} omitted). Omission does not imply unlisted sites passed.",
                        empty_notice_style,
                    )
                )
                story.append(Spacer(1, 2))

            displayed_regions = region_ev[:max_regions]

            reg_headers = [
                Paragraph("Site ID", cell_header),
                Paragraph("Status", cell_header),
                Paragraph("Current Measurements (15 scalar snapshot)", cell_header),
                Paragraph("Reference Measurements", cell_header),
            ]
            reg_rows = [reg_headers]

            for entry in displayed_regions:
                if not isinstance(entry, dict):
                    reg_rows.append([
                        Paragraph("Malformed", cell_small_bold),
                        Paragraph("UNKNOWN", cell_small_normal),
                        Paragraph("Malformed region entry (expected dictionary record).", cell_small_normal),
                        Paragraph("-", cell_small_normal),
                    ])
                    continue

                # Read canonical roi_id (do NOT fallback to noncontract site_id alias)
                raw_roi_id = entry.get("roi_id")
                if raw_roi_id is None or not isinstance(raw_roi_id, (str, int, float)):
                    site_id_str = "UNKNOWN"
                else:
                    site_id_str = _truncate_str(str(raw_roi_id), max_len=200)

                curr_m = entry.get("current_measurements")
                ref_m = entry.get("reference_measurements")

                if not isinstance(curr_m, dict):
                    curr_text = "Malformed current measurement data."
                    curr_status = "UNKNOWN"
                else:
                    # Read nested inspection_status strictly from curr_m and validate against enum
                    raw_status = curr_m.get("inspection_status")
                    if isinstance(raw_status, str) and raw_status in ALLOWED_INSPECTION_STATUSES:
                        curr_status = raw_status
                    else:
                        curr_status = "UNKNOWN"

                    cal_d = curr_m.get("calibrated_diameter_mm")
                    if cal_d is None:
                        cal_d_str = "Not recorded"
                    elif _is_finite_number(cal_d):
                        raw_cal_str = f"{float(cal_d):.3f} mm"
                        if len(raw_cal_str) > 200:
                            cal_d_str = f"{raw_cal_str[:200]} <font color='#b45309'>[truncated (exceeds 200 chars)]</font>"
                        else:
                            cal_d_str = raw_cal_str
                    else:
                        cal_d_str = "unavailable"

                    dep_area_str = _fmt_num(curr_m.get("deposit_area_px"))
                    tgt_area_str = _fmt_num(curr_m.get("target_area_px"))
                    area_dep = f"{dep_area_str} px&sup2;" if dep_area_str not in ("-", "unavailable") else dep_area_str
                    area_tgt = f"{tgt_area_str} px&sup2;" if tgt_area_str not in ("-", "unavailable") else tgt_area_str

                    diam_px_str = _fmt_num(curr_m.get("equivalent_diameter_px"))
                    diam_px = f"{diam_px_str} px" if diam_px_str not in ("-", "unavailable") else diam_px_str

                    curr_parts = [
                        f"<b>Coverage:</b> {_fmt_num(curr_m.get('coverage_ratio'))} | <b>Overflow:</b> {_fmt_num(curr_m.get('overflow_ratio'))}",
                        f"<b>Area:</b> {area_dep} (tgt: {area_tgt})",
                        f"<b>Diam:</b> {diam_px} | <b>Phys:</b> {cal_d_str}",
                        f"<b>Shape:</b> circ={_fmt_num(curr_m.get('circularity'))}, sol={_fmt_num(curr_m.get('solidity'))}, conv={_fmt_num(curr_m.get('convexity'))}, asp={_fmt_num(curr_m.get('aspect_ratio'))}",
                        f"<b>Voids/Bubbles:</b> void={_fmt_num(curr_m.get('hole_void_ratio'))}, bubbles={_fmt_num(curr_m.get('bubble_count'))} (has={_fmt_bool(curr_m.get('has_bubbles'))})",
                        f"<b>Seg Quality:</b> {_fmt_num(curr_m.get('segmentation_quality'))}",
                    ]
                    curr_text = "<br/>".join(curr_parts)

                if ref_m is None:
                    ref_text = "None (not in reference mode or unmatched)"
                elif not isinstance(ref_m, dict):
                    ref_text = "Malformed reference measurement data."
                else:
                    ref_raw_status = ref_m.get("inspection_status")
                    if isinstance(ref_raw_status, str) and ref_raw_status in ALLOWED_INSPECTION_STATUSES:
                        ref_status_str = ref_raw_status
                    else:
                        ref_status_str = "UNKNOWN"

                    ref_cal_d = ref_m.get("calibrated_diameter_mm")
                    if ref_cal_d is None:
                        ref_cal_str = "Not recorded"
                    elif _is_finite_number(ref_cal_d):
                        raw_ref_cal_str = f"{float(ref_cal_d):.3f} mm"
                        if len(raw_ref_cal_str) > 200:
                            ref_cal_str = f"{raw_ref_cal_str[:200]} <font color='#b45309'>[truncated (exceeds 200 chars)]</font>"
                        else:
                            ref_cal_str = raw_ref_cal_str
                    else:
                        ref_cal_str = "unavailable"

                    ref_dep_area_str = _fmt_num(ref_m.get("deposit_area_px"))
                    ref_tgt_area_str = _fmt_num(ref_m.get("target_area_px"))
                    ref_area_dep = f"{ref_dep_area_str} px&sup2;" if ref_dep_area_str not in ("-", "unavailable") else ref_dep_area_str
                    ref_area_tgt = f"{ref_tgt_area_str} px&sup2;" if ref_tgt_area_str not in ("-", "unavailable") else ref_tgt_area_str

                    ref_diam_px_str = _fmt_num(ref_m.get("equivalent_diameter_px"))
                    ref_diam_px = f"{ref_diam_px_str} px" if ref_diam_px_str not in ("-", "unavailable") else ref_diam_px_str

                    ref_parts = [
                        f"<b>Status:</b> {ref_status_str}",
                        f"<b>Coverage:</b> {_fmt_num(ref_m.get('coverage_ratio'))} | <b>Overflow:</b> {_fmt_num(ref_m.get('overflow_ratio'))}",
                        f"<b>Area:</b> {ref_area_dep} (tgt: {ref_area_tgt})",
                        f"<b>Diam:</b> {ref_diam_px} | <b>Phys:</b> {ref_cal_str}",
                        f"<b>Shape:</b> circ={_fmt_num(ref_m.get('circularity'))}, sol={_fmt_num(ref_m.get('solidity'))}, conv={_fmt_num(ref_m.get('convexity'))}, asp={_fmt_num(ref_m.get('aspect_ratio'))}",
                        f"<b>Voids/Bubbles:</b> void={_fmt_num(ref_m.get('hole_void_ratio'))}, bubbles={_fmt_num(ref_m.get('bubble_count'))} (has={_fmt_bool(ref_m.get('has_bubbles'))})",
                        f"<b>Seg Quality:</b> {_fmt_num(ref_m.get('segmentation_quality'))}",
                    ]
                    ref_text = "<br/>".join(ref_parts)

                reg_rows.append([
                    Paragraph(site_id_str, cell_small_bold),
                    Paragraph(curr_status, cell_small_normal),
                    Paragraph(curr_text, cell_small_normal),
                    Paragraph(ref_text, cell_small_normal),
                ])

            reg_table = Table(reg_rows, colWidths=[75, 55, 210, 200])
            reg_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            story.append(reg_table)
            story.append(Spacer(1, 6))

    # Build the document using the NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
