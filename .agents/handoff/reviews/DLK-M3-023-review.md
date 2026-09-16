---
task_id: DLK-M3-023
reviewed_commit: 07abe45aaf56f52fc1bad918277bfb689b17b03b
decision: changes_requested
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-023

## Decision

Changes requested. The authorized dependencies, read-model reuse, in-memory response, error sanitization, concurrency pinning, and read-only design are present. Resolve the content/determinism gaps below before acceptance.

## Findings

### R1 - P1: Remove the live clock from deterministic PDF content

backend/app/services/reporting/pdf_generator.py:185 inserts datetime.now(timezone.utc) into visible PDF text. The task requires deterministic PDF text/order for unchanged persisted state and permits only timestamp information already present in the report model. Two exports seconds apart therefore differ logically even when the case is unchanged, while the acceptance criterion 'Repeated export is logically deterministic' is checked off without a repeatability test.

Use a persisted timestamp from CaseReportResponse, labeled accurately (for example, Case Created), or omit the generated timestamp. Do not fabricate a report-generation timestamp. Add a regression that renders the same report twice and compares extracted logical text/order; binary equality is not required.

### R2 - P1: Render the persisted diagnosis evidence and explanation

backend/app/services/reporting/pdf_generator.py:302-346 renders only cause ID, name, score, conclusion, and a derived status badge. CaseReportResponse already carries DiagnosisResult explanation, each cause's supporting/contradicting/neutral evidence, and persisted next_question/next_check where present. DLK-M3-023 requires the PDF to present the accepted JSON diagnosis information and specifically forbids replacing it with recomputed or invented summaries.

Render the persisted explanation and evidence with source/observation/explanation details, plus persisted next question/check when present. Use neutral empty text when absent. Do not add new diagnostic interpretation. Add focused extraction assertions using non-empty evidence and explanation fixtures.

### R3 - P2: Prove history counts and ordering against the JSON report

backend/tests/integration/test_case_report_pdf_api.py:292-321 claims same-basis coverage but only searches for identity/current-state strings and confirmed causes. It does not compare any of the four history counts or their ordering, although both the task and implementation report say it does.

Expose deterministic record counts in the PDF or otherwise make them testable, then compare PDF counts and the ordered answer/check/confirmation/lifecycle values against the JSON arrays. Avoid weak assertions such as checking that the digit '7' occurs somewhere.

### R4 - P2: Complete visual layout verification

The tests parse text and confirm multiple pages, but text extraction cannot detect clipped or overlapping cells. No visual render/inspection evidence is recorded for the rich, empty, long-text, and multi-page cases. This leaves the acceptance requirements for no clipping, readable wrapping, margins, and section transitions unverified.

Render representative PDFs to page images with Poppler or another approved viewer, inspect every page, and record the result in the implementation report. Keep generated review artifacts out of the commit unless the repository explicitly adopts fixtures.

### R5 - P2: Remove the unsupported confidentiality label

backend/app/services/reporting/pdf_generator.py:72 labels every page 'Confidential'. No persisted field or project contract classifies these reports as confidential. This adds handling meaning that is not part of the accepted report model. Replace it with neutral provenance text such as 'Generated from persisted diagnostic records'.

## Evidence

- Reviewed local commit 07abe45aaf56f52fc1bad918277bfb689b17b03b on backend-database.
- reportlab==5.0.1 is a runtime dependency and pypdf==6.18.1 is dev-only, matching the recorded authorization. Production code does not import pypdf.
- The PDF route calls build_case_report and renders the resulting CaseReportResponse without an independent data path. The filename uses canonical case ID and pinned revision.
- Tests cover parsing, rich/empty cases, no recalculation, successful and failing read-only behavior, concurrency, sanitization, pagination, and escaping.
- Implementer-reported verification: PDF integration 9 passed, PDF unit 4 passed, full backend 296 passed with 0 failed/skipped. Reviewer confirmed installed versions and task validation (VALID), and checked the committed diff for whitespace errors. Reviewer did not rerun PostgreSQL suites.
- No migration, persistence, native renderer, or unapproved PDF dependency was introduced.

## Follow-up

Give R1-R5 to Gemini as corrections for DLK-M3-023 and keep dependent work unreleased. Do not generate a separate task unless the user requests one. No production edits, commits, pushes, or merges performed by the reviewer.
