---
task_id: DLK-M3-023
title: Add deterministic downloadable PDF case report
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-022]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-023: Deterministic downloadable PDF case report

## Objective

Add a downloadable PDF representation of the already-accepted durable JSON case report.

Implement exactly:

`GET /api/v1/cases/{case_id}/report.pdf`

The PDF must be rendered from the **same pinned, persisted report model** already produced by DLK-M3-022.

This task must not create a second report-data path, rerun diagnosis, mutate durable state, or invent missing information.

## Current evidence

DLK-M3-022 is accepted at:

`e68015c4587b5f5afe7b14e78b2fe161dd3bf40c`

The accepted JSON report already guarantees:

- one immutable revision basis;
- histories scoped to that basis;
- current condition/defect derived consistently from the pinned revision;
- read-only behavior;
- deterministic ordering;
- no diagnostic-engine rerun;
- no durable mutation.

The PDF export must reuse those guarantees rather than reimplementing them.

## Phase A — carry forward nonblocking DLK-M3-022 documentation corrections

Before PDF work, correct only the remaining inaccurate names in the DLK-M3-022 implementation report:

- top-level field is `defect_code`, not `current_defect_code`;
- top-level field is `issue_condition`, not `current_issue_condition`;
- successful nonmutation test name is `test_report_read_only_state_proof`.

Do not change production API fields to match old prose.

## Dependency gate

Before implementation, inspect the existing backend dependency set.

### If an approved PDF renderer already exists

Use the existing renderer/library and continue.

### If no PDF renderer exists

Stop and return to the planner with:

- current dependency evidence;
- 1-2 minimal renderer options;
- license/runtime implications;
- whether each option requires native binaries;
- smallest recommended change.

Do **not** add a new production dependency without planner authorization.

Do not implement a hand-written PDF serializer.

### Planner authorization received

The dependency gate is resolved by `.agents/handoff/tasks/DLK-M3-023-dependency-authorization.md`.

Authorized exactly:

- `reportlab==5.0.1` as the production PDF renderer;
- `pypdf==6.18.1` as a test/dev-only parser and text-verification dependency.

Do not use pypdf in production application code. Do not add optional ReportLab extras, another PDF package, native rendering binaries, or system packages without returning to the planner.

## Requirements

The authoritative flow must be:

`GET /report.pdf`
-> call/reuse the accepted persisted report assembler from DLK-M3-022
-> render that report response/model into PDF
-> return PDF bytes

Do not independently query case/history tables in the PDF route when the accepted report assembler already provides the complete pinned report model.

The PDF renderer is presentation-only.

## Interfaces and data contracts

Implement:

`GET /api/v1/cases/{case_id}/report.pdf`

### Success

Return `200 OK` with:

- `Content-Type: application/pdf`
- stable filename through `Content-Disposition`

Suggested filename pattern:

`dispenseiq-case-<case_id>-r<current_revision>.pdf`

Use the actual accepted product/project naming convention if one already exists; do not rename the application in unrelated code.

### Errors

Preserve:

- `404 Not Found` — durable case missing
- sanitized `500 Internal Server Error` — unexpected report/rendering failure

Do not expose raw renderer/internal exception details.

## Implementation guidance

The JSON report model from DLK-M3-022 is the only report-data authority for this task.

The PDF layer must not:

- call `diagnose()`;
- call state-transition handlers;
- read unrestricted histories independently;
- append revisions/events;
- update case timestamps;
- infer causes or outcomes;
- fabricate absent fields.

## PDF content

The PDF must present the accepted JSON report information clearly.

At minimum include:

### Header / identity

- case ID;
- report revision;
- defect code/category available in report;
- issue condition;
- case/report timestamp information already present in the report model.

### Current diagnosis

Render the persisted current diagnosis information already present in the accepted report model.

Do not recompute or summarize beyond deterministic formatting.

### Current outcome summary

Render:

- issue condition;
- current revision;
- confirmed cause IDs;
- resolved status.

### Technician question-answer history

Render in deterministic accepted order.

### Troubleshooting-check history

Render in deterministic accepted order.

### Cause-confirmation history

Render in deterministic accepted order.

### Issue lifecycle history

Render recovery action, verification, and recurrence events in deterministic accepted order.

## Formatting requirements

The output must be readable and competition-demo suitable.

At minimum:

- title/header;
- clear section headings;
- page margins;
- page numbers;
- no clipped text;
- long values wrap instead of overflowing;
- empty-history sections display a clear neutral value such as `None recorded`;
- multi-page histories continue safely across pages;
- deterministic section ordering.

Do not add decorative content that changes diagnostic meaning.

Do not use generative/LLM-written narrative.

## Determinism

For an unchanged persisted case state and same application version:

- JSON report logical content remains unchanged;
- PDF text/order must be deterministic;
- filename must be deterministic from case/revision;
- repeated export must not create database changes.

Binary byte-for-byte equality is desirable but not mandatory if the renderer embeds unavoidable creation metadata.

If byte equality is not guaranteed, tests must compare normalized/extracted document content and structural properties instead.

## Read-only proof

For a rich case:

1. capture complete durable state;
2. request `/report.pdf`;
3. verify successful PDF response;
4. capture state again in a fresh independent session;
5. assert exact durable-state equality.

No case, observation, revision, answer, check, confirmation, or lifecycle row may change.

## Same-basis proof

The PDF and JSON report for the same unchanged case must describe the same revision basis.

At minimum assert:

- same case ID;
- same current revision;
- same defect code;
- same issue condition;
- same confirmed causes;
- same event/history ordering and counts.

Do not create a second pinning strategy for PDF.

## Concurrent-write consistency

Reuse the accepted JSON report assembler's pinned-revision consistency.

Add a regression where a valid writer advances the case after the PDF request has selected its report basis.

The PDF must still describe one coherent pinned revision and must not mix later lifecycle history into the earlier report.

The database may advance concurrently; the PDF itself must remain internally consistent.

## Failure sanitization

Add a bounded renderer-failure test using a synthetic sensitive marker/private path.

Assert:

- `500`;
- sensitive marker absent from response;
- complete durable state unchanged.

Also retain/report-assembler failure sanitization through existing behavior.

## PDF validity verification

Tests must verify that returned bytes are a valid parseable PDF using the already-approved PDF stack.

At minimum verify:

- PDF signature/parse success;
- one or more pages;
- expected case/revision text present;
- required major section headings present;
- rich-history values appear;
- long content does not make rendering fail.

If the chosen renderer/parser is the same library, add at least one independent lightweight validity check available in the existing environment when practical.

## No persistence

Do not add:

- report table;
- generated-file table;
- object storage;
- cached PDF blob;
- report audit event;
- migration.

This endpoint generates the PDF on request from the accepted persisted report read model.

## Performance boundary

This task is not a caching/performance project.

Do not add:

- background jobs;
- queues;
- persistent cache;
- Redis;
- async document workers.

If rendering a normal rich test case exceeds current request-time constraints materially, return evidence to the planner before introducing infrastructure.

## Allowed paths

- existing report API route module, likely `backend/app/api/cases.py`
- existing report schema/service modules from DLK-M3-022
- one focused PDF renderer module under `backend/app/services/` if appropriate
- `backend/tests/integration/test_case_report_pdf_api.py`
- focused unit renderer test file if useful
- `backend/tests/case_snapshot_helper.py` only if required for read-only proof
- `docs/api/api-spec.md`
- `backend/README.md` only for small export documentation
- dependency manifest/lock files **only if planner separately authorizes a new PDF dependency after the dependency gate**
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/NEXT-STEPS.md`
- `.agents/handoff/reviews/DLK-M3-022-review.md` unchanged
- `.agents/handoff/tasks/DLK-M3-022-case-report-export.md` only for Phase A documentation corrections
- `.agents/handoff/tasks/DLK-M3-023-pdf-report-export.md`

Return to the planner before editing outside this scope.

## Prohibited scope

Do not:

- change JSON report contract;
- create a second report assembler;
- add database migrations/tables;
- persist PDF files;
- add new dependency without planner authorization;
- add DOCX export;
- add LLM narrative;
- add historical-case retrieval;
- add CV/image analysis;
- add frontend/auth;
- change workflow semantics;
- rerun diagnosis.

## Acceptance criteria

### Dependency gate

- [x] Existing backend PDF capability is identified and documented.
- [x] No unapproved production dependency is added.
- [x] If no approved renderer exists, task is marked blocked before implementation.

### Endpoint

- [x] `GET /api/v1/cases/{case_id}/report.pdf` exists.
- [x] Existing case returns `200`.
- [x] Response `Content-Type` is `application/pdf`.
- [x] `Content-Disposition` filename includes case ID and pinned revision.
- [x] Missing case returns `404`.
- [x] Unexpected render failure returns sanitized `500`.

### Source of truth

- [x] PDF is rendered from the accepted DLK-M3-022 report model.
- [x] No diagnostic recalculation occurs.
- [x] No independent unrestricted history reads create a second consistency path.
- [x] PDF and JSON exports agree on case/revision/current state/history basis.

### Content/layout

- [x] Major report sections render.
- [x] Rich histories render in deterministic order.
- [x] Empty histories render cleanly.
- [x] Long text wraps safely.
- [x] Multi-page output is supported.
- [x] Page numbering/margins are present.
- [x] No diagnostic meaning is invented.

### Consistency/read-only

- [x] Repeated export is logically deterministic.
- [x] Concurrent writer regression still yields one coherent pinned report basis.
- [x] Complete durable state before/after export is identical.
- [x] Failure-path export also leaves durable state unchanged.

### PDF validity

- [x] Returned bytes parse as a valid PDF.
- [x] Expected case/revision text is extractable/present.
- [x] Required headings are present.
- [x] At least one multi-page/rich-history case is verified.

### Regression

- [x] JSON report API remains unchanged.
- [x] recurrence workflow passes.
- [x] recovery-verification workflow passes.
- [x] cause-confirmation workflow passes.
- [x] check-result workflow passes.
- [x] question-answer workflow passes.
- [x] persistence/safety suites pass.
- [x] full backend suite passes.
- [x] no migration/schema change.
- [x] only authorized files change.
- [x] no remote Git operation occurs.

### Documentation carry-forward

- [x] DLK-M3-022 report uses `defect_code`.
- [x] DLK-M3-022 report uses `issue_condition`.
- [x] DLK-M3-022 report names `test_report_read_only_state_proof` correctly.
- [x] Production JSON report contract is unchanged.

## API documentation

Update `docs/api/api-spec.md` with:

- PDF route;
- response media type;
- deterministic filename convention;
- `200/404/500`;
- statement that PDF uses the same pinned persisted report basis as JSON;
- statement that PDF export performs no mutation or recalculation;
- limitation that PDF is generated on request and not persisted.

## Verification

Use the accepted local PostgreSQL test database.

From `backend/`, run at minimum:

1. PDF report API suite:
   `./.venv/Scripts/python.exe -m pytest -q tests/integration/test_case_report_pdf_api.py`

2. PDF renderer unit tests if created;

3. JSON case-report API/unit suites;

4. recurrence suite;

5. recovery-verification suite;

6. cause-confirmation suite;

7. check-result + semantic suites;

8. question-answer suites;

9. persistence suite;

10. persistence-safety suite;

11. durable case + diagnosis + health suites;

12. full backend:
    `./.venv/Scripts/python.exe -m pytest -q`

13. inspect OpenAPI and verify both JSON/PDF report routes and all prior routes remain stable.

From repository root:

14. validate task:
    `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-023-pdf-report-export.md`

15. `git diff --check`

16. inspect `git status`, staged names, and full staged diff.

If real PostgreSQL verification cannot run, mark the task `blocked`.

## Planner decision boundaries

Return to the planner before:

- adding any PDF library/dependency;
- adding native rendering binaries;
- adding report persistence/storage;
- changing JSON report fields;
- adding DOCX;
- adding caching/background workers;
- adding historical retrieval/LLM narrative;
- changing workflow/domain semantics.

## Git instructions

After all acceptance criteria pass:

- complete the DLK-M3-023 implementation report;
- mark DLK-M3-023 and `QUEUE.md` as `implemented`;
- inspect staged files/diff;
- create one atomic local commit.

Proposed commit message:

`feat(api): add downloadable PDF case report`

Do not push, merge, rebase, create/update a pull request, or modify `main`.

## Implementation report

### Summary
Implemented the deterministic downloadable PDF case report endpoint `GET /api/v1/cases/{case_id}/report.pdf` using authorized libraries `reportlab==5.0.1` and `pypdf==6.18.1`. The PDF report is rendered directly in memory from the accepted, immutable `CaseReportResponse` read model produced by `build_case_report` (DLK-M3-022). The endpoint creates zero database mutations, executes in a read-only transaction, performs zero diagnostic recalculations, reads no secondary unpinned data paths, and introduces no PDF persistence. Includes multi-page flowable formatting, running header and footer with dynamic "Page X of Y" pagination via a two-pass `NumberedCanvas`, table word-wrapping, and neutral notices ("None recorded.") for empty histories. In Phase A, carried forward DLK-M3-022 report documentation corrections.

### Files changed
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-023 status to `implemented`.
- `.agents/handoff/tasks/DLK-M3-022-case-report-export.md`: Completed Phase A documentation corrections (`defect_code`, `issue_condition`, `test_report_read_only_state_proof`).
- `.agents/handoff/tasks/DLK-M3-023-pdf-report-export.md`: Updated status to `implemented`, checked off all acceptance criteria, and recorded full implementation report.
- `backend/pyproject.toml`: Added `reportlab==5.0.1` to runtime dependencies and `pypdf==6.18.1` to dev dependencies per planner authorization.
- `backend/app/services/reporting/pdf_generator.py`: PDF rendering service using ReportLab flowables, tables, and custom `NumberedCanvas`.
- `backend/app/services/reporting/__init__.py`: Exported `render_case_report_pdf`.
- `backend/app/api/cases.py`: Added `GET /api/v1/cases/{case_id}/report.pdf` endpoint with 200, 404, 422, and sanitized 500.
- `backend/tests/unit/test_pdf_generator.py`: 4 unit tests covering rich PDF structure, empty history, long text wrapping, and multi-page pagination.
- `backend/tests/integration/test_case_report_pdf_api.py`: 9 integration tests covering OpenAPI, empty history, 7-revision rich history, same-basis proof, no-recalculation proof, read-only proof, concurrent update consistency, 404/422 handling, and sanitized 500 nonmutation proof.
- `docs/api/api-spec.md`: Documented Section 10 (Downloadable PDF Case Report Export).

### Phase A DLK-M3-022 documentation corrections
Updated `.agents/handoff/tasks/DLK-M3-022-case-report-export.md` to use the canonical schema field names `defect_code` and `issue_condition` (instead of `current_defect_code` and `current_issue_condition`) and corrected the read-only proof test name to `test_report_read_only_state_proof`. No production API contracts or code were altered.

### Dependency gate result
- **Dependencies authorized**: `reportlab==5.0.1` (production runtime renderer) and `pypdf==6.18.1` (dev test dependency) per `.agents/handoff/tasks/DLK-M3-023-dependency-authorization.md`.
- **Installed & verified**: Both packages installed into `backend/.venv`; verified imports: `reportlab: 5.0.1`, `pypdf: 6.18.1`. `pypdf` is strictly confined to tests (`test_pdf_generator.py`, `test_case_report_pdf_api.py`) and is never imported by production application code.

### PDF route/rendering design
- Route: `GET /api/v1/cases/{case_id}/report.pdf`
- Status codes: `200 OK`, `404 Not Found`, `422 Unprocessable Entity` (invalid UUID), `500 Internal Server Error` (sanitized).
- Flow: Validates case ID -> calls `build_case_report(case_id, repository)` -> calls `render_case_report_pdf(report)` -> returns `Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="dispenseiq-case-{case_id}-r{current_revision}.pdf"'})`.
- Rendering layout:
  - Document header with title, case ID, revision, generated timestamp.
  - Section 1: Case Identity & Process Context (case ID, revision, defect category, defect name, issue condition, material, method, problem description, machine context).
  - Section 2: Current Outcome Summary (condition, revision basis, confirmed causes, resolved status).
  - Section 3: Current Diagnosis Snapshot (analysis revision, ranked causes with scores and conclusions).
  - Section 4: Technician Question-Answer History (ascending revision/timestamp table or "None recorded.").
  - Section 5: Troubleshooting-Check History (ascending revision/timestamp table or "None recorded.").
  - Section 6: Cause-Confirmation History (ascending revision/timestamp table or "None recorded.").
  - Section 7: Issue Lifecycle History (ascending revision/timestamp table or "None recorded.").
  - Two-pass `NumberedCanvas` renders running header line and running footer with dynamic "Page X of Y" pagination.

### Same-basis and read-only proof
- **Same-basis proof**: `test_pdf_report_same_basis_as_json_report` asserts that for an unchanged case, the PDF filename and extracted document text describe the identical case ID, current revision, defect code, issue condition, confirmed causes, and history counts as `GET /api/v1/cases/{case_id}/report`.
- **Zero-recalculation proof**: `test_pdf_report_no_recalculation_proof` patches `DiagnosticEngine.diagnose` to raise a `RuntimeError` and proves that `GET /report.pdf` succeeds with 200 without invoking diagnostic calculation.
- **Read-only proof**: `test_pdf_report_read_only_state_proof` captures full database state before and after GET in fresh independent sessions, asserting 100% exact equality across cases, revisions, and histories.
- **Concurrent-write consistency**: `test_pdf_report_consistency_under_concurrent_update` interleaves a recurrence commit (rev 7 `RECURRED`) via independent session while PDF assembly is in flight. Asserts returned PDF is named `dispenseiq-case-{case_id}-r6.pdf` and describes rev 6 (`RESOLVED`) consistently, excludes rev 7 recurrence event, and proves PDF generation wrote nothing.
- **Sanitized-500 nonmutation proof**: `test_pdf_report_sanitized_500_on_internal_error` simulates an internal rendering error with a sensitive marker; proves status 500, detail is sanitized, sensitive token is absent, and database state before/after is strictly identical.

### Verification results
Ran verified test suites against local PostgreSQL (`dispenselens-postgres`):
1. `tests/integration/test_case_report_pdf_api.py`: 9 passed in 6.17s
2. `tests/unit/test_pdf_generator.py`: 4 passed in 0.91s
3. `tests/integration/test_case_report_api.py`: 9 passed in 5.23s
4. `tests/unit/test_report_generator.py`: 8 passed in 0.70s
5. `tests/integration/test_recurrence_api.py`: 9 passed in 5.16s
6. `tests/integration/test_recovery_verification_api.py`: 23 passed in 5.86s
7. `tests/integration/test_cause_confirmation_api.py`: 17 passed in 4.79s
8. Check result & semantic suites: 78 passed in 5.34s
9. Question answer suites: 34 passed in 3.59s
10. Persistence & core API suites: 80 passed in 9.88s
11. Full backend test suite (`pytest -q`): **296 passed**, 31 warnings, **0 failed**, **0 skipped** in 44.82s.
12. OpenAPI schema verified: `GET /api/v1/cases/{case_id}/report.pdf` registered with 200, 404, 422, 500 status codes.
13. Packet validation: `python .agents/skills/implementation-handoff/scripts/validate_task.py` passed with `VALID`.
14. Diff hygiene: `git diff --check` passed cleanly with no whitespace or EOF errors.

### Limitations and follow-up
- PDF generation is rendered on-demand in memory; no persistent PDF files or blob storage were introduced.
- Historical case similarity and LLM narration remain deferred to future authorized tasks.

### Proposed commit message
`feat(api): add downloadable PDF case report`
