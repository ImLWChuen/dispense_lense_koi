---
task_id: DLK-M3-023
reviewed_commit: 32a9a2137d42bf9dcfbbb5b6305463c730da74f1
decision: changes_requested
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-023

## Latest re-review (supersedes the decision and findings below)

**Decision: changes_requested.** Reviewed correction commit `32a9a2137d42bf9dcfbbb5b6305463c730da74f1` on `backend-database`. One acceptance-test correction remains; no new production-code defect was identified in the correction diff.

### R3 remaining - P2: Scope ordering assertions to actual history rows

`backend/tests/integration/test_case_report_pdf_api.py:349-389` searches the entire PDF independently for IDs/event types and checks associated values only for presence. A cause ID can match the outcome summary or diagnosis table before its confirmation row. Repeated IDs/types and independently matched values do not establish row identity or correspondence. The fixture also has only one answer, one check, and one confirmation, so reversing those histories cannot fail this test. Exact count headers are now covered, but the required ordering proof remains incomplete.

Correction for Gemini/planner: restrict extraction to each numbered history section; use at least two distinguishable entries per history in a focused renderer fixture where the API workflow cannot naturally supply them. Compare ordered row-specific tuples/markers (ID or event type plus revision, timestamp, answer/outcome/actor as appropriate) against the corresponding report arrays. Include repeated IDs/event types with distinguishable row values. Ensure a reversed row sequence or a value associated with the wrong row fails the assertions. Retain the real API JSON/PDF same-basis test and exact counts. Update the implementation report to describe the actual coverage; it currently overstates timestamp/order verification. No separate task packet was generated.

### Previous finding disposition

- R1 resolved in code: the visible live clock was replaced with persisted `Case Created`; a logical text repeatability test was added.
- R2 resolved in code: stored explanation, supporting/contradicting/neutral evidence, next question and next check are rendered with neutral empty states. Non-empty evidence fixtures were added.
- R3 partially resolved: exact counts added; ordering gap above remains.
- R4: implementer supplied a four-fixture, ten-page rendering report. This is implementer-reported evidence, not independent reviewer visual verification: access to the temporary artifact directory was denied in this session. Minor documentation correction: 1224 x 1584 pixels for US Letter corresponds to 144 DPI, not 150 DPI. Page-wide bounding boxes alone cannot prove absence of internal cell overlap; describe actual visual inspection separately if performed.
- R5 resolved: unsupported confidentiality label replaced with neutral provenance text.

### Verification and boundaries

- Reviewer inspected the correction diff and relevant test fixtures, confirmed task validation returned `VALID`, and checked the committed diff for whitespace errors (passed).
- Gemini reports PDF integration 9 passed, PDF unit 5 passed, and full backend 297 passed with no failures/skips. These suites were not rerun by the reviewer, consistent with the project planner/executor split.
- Review and queue records updated only. No production corrections, new task, commit, push, or merge performed.

## Prior review of 07abe45 (historical)

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
