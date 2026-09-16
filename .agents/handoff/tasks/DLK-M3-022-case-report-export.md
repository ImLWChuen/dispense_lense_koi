---
task_id: DLK-M3-022
title: Add deterministic durable case report export API
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-021]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-022: Deterministic durable case report export API

## Objective

Add a read-only report/export endpoint for a durable diagnostic case:

`GET /api/v1/cases/{case_id}/report`

The report must be assembled only from persisted case state and persisted audit history.

It must not rerun diagnosis, append revisions, mutate workflow state, fabricate missing information, or persist generated reports.

PDF/document rendering is deferred.

## Current evidence

DLK-M3-021 is accepted at:

`ff8a4d9ccaef2f7be2dc539c77cf4c46d963739f`

The durable workflow now covers initial diagnosis, question answers, troubleshooting checks, explicit cause confirmation, recovery action, recovery verification, recurrence reporting, immutable revisions, and append-only audit histories.

## Phase A — carry forward DLK-M3-021 documentation corrections

Before new report work, correct only the inaccurate names in the DLK-M3-021 implementation report.

Use actual code/API specification as authority.

Correct to:

- `append_recurrence_revision`
- `append_lifecycle_event_revision`
- `transition_issue_condition`
- `current_revision`
- `submitted_recurrence`
- `submitted_event`
- `lifecycle_events`
- `diagnosis.analysis_revision`
- lifecycle-event actor field `actor`

Remove/replace inaccurate report references to:

- `append_recurrence_event`
- `append_lifecycle_event`
- `record_recurrence`
- `lifecycle_event`
- `revision`
- `source_event_type`
- `source_event_id`
- recurrence event `reported_by`

Do not change production recurrence code to match the old report.

## Requirements

The report is a deterministic persisted-state read model.

For unchanged database state, repeated GETs must return the same logical content.

The endpoint must not:

- call `diagnose()`;
- invoke question/check/confirmation/recovery/recurrence transition logic;
- change current revision;
- write audit rows;
- update timestamps;
- infer missing technician answers;
- guess unknown values.

## Interfaces and data contracts

`GET /api/v1/cases/{case_id}/report`

Status codes:

- `200 OK`
- `404 Not Found`
- sanitized `500 Internal Server Error`

No `expected_revision` is required because this is read-only.

## Report contents

Create a dedicated response schema. Do not expose raw ORM objects.

Include, at minimum:

### Case/report basis

- `case_id`
- `current_revision`
- current persisted defect/category information
- current issue condition
- persisted case creation timestamp if already available in the durable case contract

### Current diagnosis snapshot

Use only the latest persisted analysis snapshot.

Include current persisted diagnosis information already available through accepted contracts, such as:

- defect/category;
- ranked causes;
- evidence-support scores;
- cause conclusions;
- supporting/contradicting evidence;
- persisted explanations;
- persisted next-question/check information where present.

Do not rerun the engine to populate absent fields.

### Question-answer history

Include all persisted technician answer events in deterministic order, preserving accepted durable meaning and stored values.

### Troubleshooting-check history

Include all persisted check-result events, preserving:

- action/check ID;
- execution status;
- finding;
- submitted outcome/result;
- revision;
- timestamp;
- stored actor/details where available.

Do not reinterpret check outcomes.

### Cause-confirmation history

Include explicit persisted confirmations, preserving cause ID, revision, actor/note fields from the accepted confirmation contract, and timestamp.

### Issue-lifecycle history

Include persisted lifecycle events, including recovery action, verification, and recurrence.

Preserve the actual accepted lifecycle-event contract, including event type, prior/resulting condition, revision, `actor`, details, verification outcome where applicable, and timestamp.

### Current outcome summary

Provide a compact direct projection of current persisted state:

- current issue condition;
- current revision;
- currently confirmed cause IDs based on persisted cause conclusions;
- whether the issue is currently resolved.

This must not be a new diagnostic inference.

## Deterministic ordering

All history arrays must have explicit stable ordering.

Prefer:

1. accepted revision ascending;
2. creation timestamp ascending when needed;
3. stable persisted identifier as final tie-breaker if one exists.

Do not rely on implicit ORM/database ordering.

## No recalculation proof

Add a regression that makes engine recalculation fail if called, while report GET still returns `200` from persisted state.

## Read-only proof

For a case with rich history:

1. capture complete durable state;
2. GET the report;
3. capture state again in a fresh independent session;
4. assert exact equality.

Verify no change to case, observations, revisions, answers, checks, confirmations, or lifecycle events.

## Rich-history scenario

Exercise a realistic persisted workflow including as many valid event types as domain semantics allow:

- initial diagnosis;
- question answer;
- check result;
- cause confirmation where valid;
- recovery action;
- recovery verification;
- recurrence if the case reaches `RESOLVED`.

Verify each persisted event appears exactly once in the correct report section.

Do not weaken domain semantics merely to force all event types into one fixture.

## Empty-history behavior

A newly created case with no later technician actions must still return a valid report with clean empty history structures.

Do not fabricate placeholder activity.

## Historical accuracy

Latest diagnosis section represents latest persisted analysis.

History sections represent the actual accepted event history.

Do not rewrite old events from current state.

## Security

Unexpected internal report-assembly failures must return sanitized `500`.

Add a synthetic-sensitive-marker regression proving:

- `500`;
- sensitive marker absent;
- no durable mutation.

## Persistence/model scope

Prefer no migration and no new table.

This is a read projection over accepted persistence.

If required report data cannot be read from current accepted storage without schema changes, stop and return the exact gap to the planner.

## Implementation guidance

Prefer:

`GET route -> repository reads -> focused report assembler -> response schema`

The assembler must be deterministic and side-effect free.

Follow existing project conventions; add no new framework/dependency.

## Allowed paths

- `backend/app/api/cases.py`
- `backend/app/schemas/case.py` or an existing focused report schema module
- `backend/app/services/` for one bounded report-assembly module if appropriate
- `backend/app/db/repository.py` only for complete read access
- `backend/tests/integration/test_case_report_api.py`
- focused unit report tests if a new service is created
- `backend/tests/case_snapshot_helper.py` if needed for read-only comparison
- `docs/api/api-spec.md`
- `backend/README.md` only for small report documentation
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/NEXT-STEPS.md`
- `.agents/handoff/reviews/DLK-M3-021-review.md` unchanged
- `.agents/handoff/tasks/DLK-M3-021-recurrence-api.md` only for Phase A report corrections
- `.agents/handoff/tasks/DLK-M3-022-case-report-export.md`

Return to the planner before editing outside this scope.

## Prohibited scope

Do not:

- add migrations/report tables;
- persist reports;
- generate PDF/DOCX;
- rerun diagnostic logic;
- alter scoring/evidence/workflow semantics;
- add historical similarity/search;
- add LLM-generated narrative;
- add CV/image analysis;
- add frontend/auth;
- add generic export frameworks/dependencies.

## Acceptance criteria

- [x] `GET /api/v1/cases/{case_id}/report` exists.
- [x] Existing case returns `200`.
- [x] Missing case returns `404`.
- [x] Unexpected internal failure returns sanitized `500`.
- [x] Report uses latest persisted analysis snapshot.
- [x] Diagnostic engine is not rerun.
- [x] No workflow transition is invoked.
- [x] No mutation/revision/event is created.
- [x] Repeated GETs over unchanged state are logically deterministic.
- [x] Case identity/current revision/current issue condition included.
- [x] Current persisted diagnosis included.
- [x] Answer history included.
- [x] Check history included.
- [x] Confirmation history included.
- [x] Lifecycle history included.
- [x] Current outcome summary included.
- [x] Empty history is represented without fabricated events.
- [x] History ordering is explicit and tested.
- [x] Rich-case state is exactly unchanged before/after GET.
- [x] DLK-M3-021 implementation report names are corrected as required.
- [x] No production recurrence contract is changed.
- [x] All workflow/persistence/safety/full-backend regressions pass.
- [x] No schema/migration change.
- [x] Only authorized files change.
- [x] No remote Git operation occurs.

## Documentation

Update `docs/api/api-spec.md` with:

- route and response shape;
- `200/404/500`;
- persisted-state authority;
- no diagnostic recalculation;
- no mutation;
- deterministic history ordering;
- separation between latest diagnosis snapshot and chronological audit history.

Do not claim PDF export is implemented.

## Verification

From `backend/` using verified PostgreSQL:

1. `./.venv/Scripts/python.exe -m pytest -q tests/integration/test_case_report_api.py`
2. report unit tests if created
3. recurrence API suite
4. recovery-verification suite
5. cause-confirmation suite
6. check-result + semantic suites
7. question-answer suites
8. persistence suite
9. persistence-safety suite
10. durable case + diagnosis + health suites
11. `./.venv/Scripts/python.exe -m pytest -q`
12. inspect OpenAPI

From repo root:

13. validate this task packet
14. `git diff --check`
15. inspect status, staged file names, and staged diff

If PostgreSQL verification cannot run, mark the task `blocked`.

## Planner decision boundaries

Return to the planner before:

- adding report persistence/migrations;
- adding PDF rendering;
- rerunning diagnosis;
- inventing missing data;
- adding LLM narrative;
- adding historical-case retrieval;
- changing existing workflow contracts;
- adding dependencies.

## Git instructions

After all criteria pass:

- complete implementation report;
- mark DLK-M3-022 and queue `implemented`;
- create one atomic local commit:

`feat(api): add durable case report export`

Do not push, merge, rebase, create/update a PR, or modify `main`.

## Implementation report

### Summary
Implemented the deterministic durable case report export endpoint `GET /api/v1/cases/{case_id}/report`. The endpoint projects a complete read-model of a troubleshooting case strictly from persistent database storage (`cases`, `analysis_revisions`, `question_answer_revisions`, `check_result_revisions`, `cause_confirmation_revisions`, and `case_lifecycle_events`). The endpoint executes in a read-only transaction, performs zero diagnostic recalculation, invokes no domain workflow transitions, creates zero revisions or lifecycle events, and does not alter database timestamps or state. All audit histories are returned in strict ascending revision and timestamp order. In Phase A, corrected prior DLK-M3-021 implementation report naming inconsistencies. Following reviewer findings (R1, R2, R3), ensured report assembly consistency under concurrent updates by pinning an immutable revision basis across all fields and histories, added a complete failure-path nonmutation proof around the sanitized 500 scenario, and corrected verification and contract documentation.

### Files changed
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-022 status from `in_progress` to `implemented`.
- `.agents/handoff/tasks/DLK-M3-021-recurrence-api.md`: Corrected Phase A implementation report attribute and method names (`append_recurrence_revision`, `append_lifecycle_event_revision`, `transition_issue_condition`, `current_revision`, `submitted_recurrence`, `submitted_event`, `lifecycle_events`, `diagnosis.analysis_revision`, `actor`).
- `.agents/handoff/tasks/DLK-M3-022-case-report-export.md`: Task definition, acceptance criteria, and full implementation report updated with R1-R3 corrections and exact test counts.
- `backend/app/schemas/case.py`: Added `CaseOutcomeSummary` and `CaseReportResponse` Pydantic models with field aliases for flexible consumption and `extra="forbid"`.
- `backend/app/db/repository.py`: Added `get_latest_analysis_revision(case_id)` to fetch the highest revision snapshot cleanly in read-only mode.
- `backend/app/services/reporting/__init__.py`: Exported `build_case_report`.
- `backend/app/services/reporting/report_generator.py`: Pure, side-effect-free report assembly service sorting all audit records deterministically, pinning the revision basis, and projecting the analysis revision, histories scoped with `max_revision`, and outcome summary.
- `backend/app/api/cases.py`: Added `GET /api/v1/cases/{case_id}/report` endpoint handling 200, 404, 422, and sanitized 500.
- `backend/tests/unit/test_report_generator.py`: 8 isolated unit tests for report assembly, sorting, outcome summary, null fallbacks, missing case handling, and pinned-revision scoping.
- `backend/tests/integration/test_case_report_api.py`: 9 integration tests covering OpenAPI registration, empty history cases, 7-revision rich workflow scenarios, strict ascending chronological ordering, concurrent-update revision consistency, no-recalculation proof (engine failure injection), read-only proof (before/after complete state diffing), 404/422 handling, and sanitized 500 with synthetic sensitive marker and complete-state nonmutation verification.
- `docs/api/api-spec.md`: Documented Section 9 (Durable Case Report Export), 500 error handling example, and note 6 in frontend integration notes with exact `CaseReportResponse` contract and aliases. Explicitly documented that PDF/document export is deferred.

### Phase A DLK-M3-021 report corrections
Corrected naming inconsistencies in `.agents/handoff/tasks/DLK-M3-021-recurrence-api.md`:
- `append_recurrence_lifecycle_event` -> `append_recurrence_revision`
- `record_lifecycle_event` -> `append_lifecycle_event_revision`
- `transition_condition` -> `transition_issue_condition`
- `revision` -> `current_revision`
- `recurrence` -> `submitted_recurrence`
- `event` -> `submitted_event`
- `events` -> `lifecycle_events`
- `diagnosis.revision` -> `diagnosis.analysis_revision`
- `reported_by` in event record -> `actor`
All names in the DLK-M3-021 implementation report now precisely align with production code and API specification.

### Report API contract
- Endpoint: `GET /api/v1/cases/{case_id}/report`
- Status Codes: `200 OK`, `404 Not Found`, `422 Unprocessable Entity` (invalid UUID format), `500 Internal Server Error` (sanitized).
- Response Schema: `CaseReportResponse`
  - Case Identity & Inception: `case_id`, `current_revision`, `defect_code`, `issue_condition`, `created_at`.
  - Latest Analysis Snapshot: `diagnosis` (alias: `current_diagnosis`), representing the latest persisted `AnalysisRevision` (or initial diagnosis if no subsequent revisions exist).
  - Audit Revision Histories (each strictly sorted in ascending revision order):
    - `question_answers` (alias: `question_answer_history`)
    - `check_results` (alias: `troubleshooting_check_history`)
    - `cause_confirmations` (alias: `cause_confirmation_history`)
    - `lifecycle_events` (alias: `issue_lifecycle_history`)
  - Compact Outcome Summary: `outcome_summary` (alias: `current_outcome_summary`): `issue_condition`, `current_revision`, `confirmed_causes`, `is_resolved`.

### Persisted-state/read-only design
- Report assembly relies entirely on persistent PostgreSQL reads via `CaseRepository`.
- No calls are made to `DiagnosticEngine.diagnose()` or any symptom extraction / rule evaluation methods.
- No database write operations (`session.add`, `session.commit`, etc.) are performed; the repository transaction is read-only.
- **Consistent revision basis (R1):** `build_case_report` resolves the target revision (either explicit `pinned_revision` or latest persisted analysis revision) and pins all derived top-level fields (`current_revision`, `defect_code`, `issue_condition`), diagnosis snapshot, outcome summary, and all four history collections with `max_revision=effective_revision`. This guarantees that even under concurrent commits, the generated report reflects one coherent revision basis and writes nothing (`test_report_consistency_under_concurrent_update`).
- **Read-only proof:** Test `test_report_read_only_state_proof` captures complete database state in an independent session before and after invoking `GET /api/v1/cases/{case_id}/report`, asserting 100% exact equality across cases, revisions, and histories.
- **Sanitized-500 nonmutation proof (R2):** Test `test_report_sanitized_500_on_internal_error` captures complete durable state across independent sessions before and after a failing GET on a rich case, triggering failure after report reads have begun. It asserts HTTP 500, detail is sanitized, sensitive token absent, and before/after database state snapshots are strictly identical.
- **Zero-recalculation proof:** Test `test_report_no_recalculation_proof` patches `DiagnosticEngine.diagnose` to raise a `RuntimeError` and verifies that `GET /api/v1/cases/{case_id}/report` still returns `200 OK` from persisted data without invoking the engine.

### Ordering and deterministic projection
- `question_answers`: sorted by `revision_number ASC`, `created_at ASC`.
- `check_results`: sorted by `revision_number ASC`, `created_at ASC`.
- `cause_confirmations`: sorted by `revision_number ASC`, `created_at ASC`.
- `lifecycle_events`: sorted by `resulting_revision_number ASC`, `created_at ASC`.
- Stable tie-breakers ensure deterministic responses across repeated requests.
- Cases with empty histories return clean empty lists (`[]`) without synthetic or fabricated activity.

### Verification results
Ran verified test suites against local PostgreSQL (`dispenselens-postgres`):
1. `tests/integration/test_case_report_api.py`: 9 passed in 5.23s
2. `tests/unit/test_report_generator.py`: 8 passed in 0.70s
3. `tests/integration/test_recurrence_api.py`: 9 passed in 5.16s
4. `tests/integration/test_recovery_verification_api.py`: 23 passed in 5.86s
5. `tests/integration/test_cause_confirmation_api.py`: 17 passed in 4.79s
6. Check result & semantic suites (`test_check_result_api.py`, `test_check_result_diagnosis_revision.py`, `test_check_result_handler.py`, `test_semantic_verification.py`): 78 passed in 5.34s
7. Question answer suites (`test_question_answer_api.py`, `test_question_answer_diagnosis_revision.py`, `test_question_answer_handler.py`, `test_question_engine.py`): 34 passed in 3.59s
8. Persistence & core API suites (`test_persistence.py`, `test_persistence_safety.py`, `test_case_api.py`, `test_diagnosis_api.py`, `test_health_api.py`): 80 passed in 9.88s
9. Full backend test suite (`pytest -q`): **283 passed**, 29 warnings, **0 skipped**, **0 failed** in 40.25s.
10. OpenAPI schema verified: `GET /api/v1/cases/{case_id}/report` registered with 200, 404, 422, 500 status codes.
11. Packet validation: `python .agents/skills/implementation-handoff/scripts/validate_task.py` passed with `VALID`.
12. Diff hygiene: `git diff --check` passed cleanly with no whitespace or EOF errors.

### Limitations and follow-up
- Binary document export (PDF, Word/DOCX) is deliberately deferred; the frontend is responsible for layout, printing, or file export using the structured JSON payload.
- No database migrations or new tables were introduced; the report is purely a read model projection over existing schema.
