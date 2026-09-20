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
    # Document Header
    # ---------------------------------------------------------
    story.append(Paragraph("Dispense Lens Diagnostic Case Report", title_style))
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

    # Build the document using the NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
