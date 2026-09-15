---
task_id: DLK-M3-017
title: Add explicit durable root-cause confirmation workflow
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-016]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-017: Explicit durable root-cause confirmation workflow

## Objective

Expose an explicit technician-driven root-cause confirmation workflow for an existing durable diagnostic case.

A supporting troubleshooting check, high evidence-support score, or high-ranked hypothesis must not confirm a cause automatically.

A client must explicitly confirm a selected cause. The backend must then:

1. load the current durable case;
2. verify optimistic concurrency using `expected_revision`;
3. reconstruct the current `StructuredCase`;
4. invoke the existing domain `confirm_cause()` behavior;
5. preserve issue resolution independently;
6. atomically persist the confirmation event and immutable Revision N+1;
7. return the newly persisted diagnostic state.

This task must not implement issue recovery or resolution verification.

## Current evidence

- DLK-M3-016 is accepted and closes the DLK-M3-013 through DLK-M3-016 troubleshooting-check correction chain.
- Member 2's current diagnostic behavior already separates:
  - supporting check result;
  - cause confirmation;
  - issue condition/resolution.
- The existing explicit `confirm_cause()` domain operation is the semantic authority for this task.
- Core product rule:
  `check completed` != `check supports cause` != `cause confirmed` != `issue resolved`.
- After successful explicit cause confirmation:
  - the selected cause becomes `CONFIRMED` according to the existing domain contract;
  - the issue condition must not automatically become resolved;
  - no recovery/verification state may be invented.

## Requirements

### 1. Product/API scope
Implement exactly one new durable workflow endpoint:
`POST /api/v1/cases/{case_id}/cause-confirmations`
Do not add bulk confirmation, unconfirm/revoke, recovery verification, issue-resolution endpoints, or generic CRUD.

### 2. Issue-condition invariant
A successful cause confirmation must not automatically resolve the issue.
Add explicit regression proof that:
- the selected cause becomes `CONFIRMED` only through explicit confirmation;
- `issue_condition` remains unresolved or otherwise non-resolved according to the existing domain state;
- this endpoint never invokes recovery/resolution behavior.

### 3. Diagnostic ownership boundary
Member 2 owns confirmation meaning.
Do not change:
- evidence rules;
- scores/thresholds;
- cause ranking;
- check mappings;
- question-answer mappings;
- `confirm_cause()` semantic rules;
- issue-resolution semantics;
- recovery semantics.
If implementation requires changing those, stop and return the blocker to the planner.

### 4. Persistence/revision requirements
Reuse the accepted case lock and global revision sequence.
Successful confirmation atomically appends:
- one confirmation-history event;
- one immutable new analysis revision.
Prior revisions must remain unchanged.
If current revision is N:
- success -> N+1;
- stale request -> no revision;
- invalid request -> no revision;
- persistence failure -> no revision.
Revision numbering must remain monotonic across question answers, check results, and cause confirmations.

### 5. Rollback verification
Prove rollback after real pending/flushed confirmation writes.
The test must:
1. establish a case with prior question-answer and check-result history;
2. allow the real append path to flush pending confirmation + revision;
3. inject failure before commit;
4. let production transaction management roll back;
5. verify in a fresh session:
   - no failed confirmation event remains;
   - no failed revision remains;
   - prior question/check histories remain unchanged;
   - prior snapshots remain unchanged;
   - unrelated control case remains unchanged.
Do not manually call rollback as the mechanism under test.

### 6. Replay protection
The stale-revision mechanism is sufficient.
After successful confirmation at expected revision N, replaying the same request with expected revision N must return `409` and append nothing.
Do not add a general idempotency-key system.

### 7. API documentation requirements
Update `docs/api/api-spec.md` with:
- exact route;
- request schema;
- successful `200`;
- stale `409`;
- invalid cause behavior;
- missing case behavior;
- explicit statement that supporting checks do not confirm a cause automatically;
- explicit statement that cause confirmation does not resolve the issue;
- optimistic-concurrency semantics;
- one confirmation -> one immutable new revision.
Do not invent fields in examples.

## Interfaces and data contracts

### 1. Request contract
Define an explicit request containing at minimum:
- `cause_id`: Validate against candidate causes for the defect. Reject unknown or invalid causes with 422 before persistence.
- `expected_revision`: Required optimistic-concurrency input (>= 1). Stale request must reject with 409 and make zero mutation.
- `confirmed_by`: Optional user/role identifier (defaults to "technician").
- `notes`: Optional technician notes stored faithfully without affecting scoring.

### 2. Successful orchestration
`HTTP request`
-> `load/lock current case`
-> `verify expected_revision`
-> `reconstruct StructuredCase`
-> `existing confirm_cause()`
-> `produce Revision N+1`
-> `atomically persist confirmation + revision`
-> `return persisted updated state`
Do not duplicate confirmation logic in the route, schema, ORM, or repository.

### 3. Durable confirmation history
Persist the explicit technician confirmation as an append-only auditable event in table `case_cause_confirmations`.
Store at minimum:
- case identity (`case_id`);
- cause ID (`cause_id`);
- revision at which confirmation was accepted (`resulting_revision_number`);
- creation timestamp (`confirmed_at`);
- confirmation performer (`confirmed_by`);
- optional note (`notes`).
The confirmation event and Revision N+1 commit in one transaction. Forward Alembic migration `0005_cause_confirmation_history.py` creates table with foreign key, unique constraint, check constraint, and index.

### 4. Response contract
Return `200 OK` on success. Expose:
- `case_id`;
- explicit persisted confirmation representation (`submitted_confirmation`);
- current revision (`current_revision`);
- updated diagnosis snapshot (`diagnosis`);
- selected cause conclusion (`selected_cause_conclusion`);
- confirmed cause (`confirmed_cause`);
- full confirmation history (`previous_confirmations`);
- check result history (`previous_check_results`);
- answer history (`previous_answers`);
- current issue condition (`issue_condition`).
The response must reflect committed state.

### 5. Status/error contract
- `200 OK` — confirmation accepted
- `404 Not Found` — case missing
- `409 Conflict` — stale `expected_revision`
- `422 Unprocessable Entity` — invalid confirmation request or unknown cause
- `500 Internal Server Error` — unexpected internal failure
Errors must not leak DB URLs, credentials, SQL, stack traces, local paths, or secrets.

## Allowed paths

- `backend/app/api/cases.py` or existing durable case route module
- `backend/app/schemas/case.py`
- `backend/app/models/case.py`
- `backend/app/models/__init__.py` if required
- `backend/app/db/repository.py`
- `backend/alembic/versions/` for one forward migration
- `backend/tests/integration/test_cause_confirmation_api.py`
- `backend/tests/integration/test_persistence.py` only for bounded persistence/rollback coverage
- existing confirmation-domain tests only for regression assertions without semantic changes
- `docs/api/api-spec.md`
- `docs/database/erd.md`
- `backend/README.md` only for small workflow documentation
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/NEXT-STEPS.md`
- `.agents/handoff/reviews/DLK-M3-016-review.md` (include unchanged)
- `.agents/handoff/tasks/DLK-M3-017-cause-confirmation-api.md`

Return to the planner before editing outside this scope.

## Prohibited scope

Do not implement:
- recovery verification;
- resolved/recurred workflow;
- confirmation revocation/unconfirm;
- report/PDF generation;
- image/CV;
- LLM integration;
- historical retrieval;
- authentication/authorization;
- frontend integration;
- generic CRUD;
- new dependencies beyond the existing persistence stack.
Do not weaken PostgreSQL test-safety rules.

## Implementation guidance

- Reconstruct `StructuredCase` via `repository.load_structured_case(case_id, max_revision=expected_revision)` populating `confirmed_causes` from `case_cause_confirmations`.
- Call `engine.confirm_cause(case, cause_id)`. Validate cause exists among candidate causes; if not, raise 422 before starting persistence.
- Enforce row lock `with_for_update()` in `append_cause_confirmation_revision()`.
- Check `latest_rev == expected_revision`, raise `StaleRevisionError` (mapped to 409) if mismatched.
- Append `CaseCauseConfirmationModel` and `AnalysisRevisionModel` atomically, flush, and commit.
- In rollback tests, use `event.listen(session, "before_commit", ...)` to inject an exception after flush, and assert in a fresh session that no rows or revisions were committed.

## Acceptance criteria

- [x] Endpoint `POST /api/v1/cases/{case_id}/cause-confirmations` is implemented and exposed in OpenAPI.
- [x] Reconstructs `StructuredCase` via `repository.load_structured_case()` and invokes existing `engine.confirm_cause()`.
- [x] Validates `cause_id` against candidate causes and rejects unknown causes with HTTP 422 before persistence.
- [x] Rejects empty `cause_id` and invalid `expected_revision < 1` with HTTP 422.
- [x] Enforces optimistic concurrency via `expected_revision`: returns HTTP 409 Conflict on stale revision or replay with zero mutations.
- [x] Forward Alembic migration `0005_cause_confirmation_history.py` creates `case_cause_confirmations` with foreign key, unique constraint, check constraint, and index.
- [x] Atomically appends one confirmation history record and one immutable Revision N+1 snapshot.
- [x] Preserves strict semantic separation: supporting checks do not confirm a cause automatically, and confirming a cause does not resolve the issue (`issue_condition` remains `UNRESOLVED`).
- [x] Rollback test proves real flushed confirmation and revision writes roll back completely on injected pre-commit failure in both API and repository layers.
- [x] Monotonic global revision numbering across question answers, check results, and cause confirmations.
- [x] Documentation updated in `docs/api/api-spec.md`, `docs/database/erd.md`, and `backend/README.md`.
- [x] All backend integration and unit tests pass (226 tests green).

## Verification

Use the accepted verified local PostgreSQL test database.

From `backend/` run at minimum:

1. `.\.venv\Scripts\python.exe -m alembic upgrade head`
2. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_cause_confirmation_api.py`
3. existing check-result API + semantic suites
4. question-answer API/revision suites
5. persistence suite
6. durable case + diagnosis + health API suites
7. persistence-safety suite
8. `.\.venv\Scripts\python.exe -m pytest -q`

Inspect OpenAPI and verify the confirmation route plus all existing routes/contracts.

From repository root:

9. `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-017-cause-confirmation-api.md`
10. `git diff --check`
11. inspect `git status`, staged names, and staged diff before commit.

If real PostgreSQL verification cannot run, mark the task `blocked`.

## Planner decision boundaries

Return to the planner before:

- changing `confirm_cause()` semantics;
- automatically confirming from score/check evidence;
- changing issue-resolution behavior;
- defining unconfirm/revocation;
- allowing confirmation to resolve the issue;
- changing existing answer/check APIs;
- adding dependencies;
- changing case/revision identity semantics;
- expanding into recovery verification.

## Git instructions

After all acceptance criteria pass:

- complete the implementation report;
- mark DLK-M3-017 and `QUEUE.md` as `implemented`;
- inspect staged files/diff;
- create one atomic local commit.

Proposed commit message:

`feat(api): add explicit cause confirmation workflow`

Do not push, merge, rebase, create/update a PR, or modify `main`.

## Implementation report

### Summary

Implemented the explicit technician root-cause confirmation workflow for durable diagnostic cases:
- Implemented `POST /api/v1/cases/{case_id}/cause-confirmations`.
- Created forward Alembic migration `0005_cause_confirmation_history.py` creating table `case_cause_confirmations` with foreign key, unique constraint `("case_id", "resulting_revision_number")`, check constraint `resulting_revision_number > 1`, and index.
- Added ORM model `CaseCauseConfirmationModel` and relationship to `CaseModel`.
- Added Pydantic schemas: `CauseConfirmationRecord`, `SubmitCauseConfirmationRequest`, `CaseCauseConfirmationResponse`.
- Added repository methods `get_case_cause_confirmations()` and `append_cause_confirmation_revision()` with row locking (`with_for_update()`), optimistic concurrency checks (`StaleRevisionError`), and atomic commit/flush.
- Reconstructed `StructuredCase` in `load_structured_case()` with `confirmed_causes` from durable confirmation history.
- Upheld semantic boundaries: checks do not confirm causes automatically, and cause confirmation does not resolve the issue (`issue_condition` remains `UNRESOLVED`).
- Implemented comprehensive integration suite in `test_cause_confirmation_api.py` (14 tests) and persistence tests in `test_persistence.py`.
- Verified pre-commit rollback on flushed confirmation/revision writes in both route and repository layers.
- Updated documentation in `docs/api/api-spec.md`, `docs/database/erd.md`, and `backend/README.md`.

### Files changed

- `backend/alembic/versions/0005_cause_confirmation_history.py`: forward migration for `case_cause_confirmations`.
- `backend/app/models/case.py`: `CaseCauseConfirmationModel` and `CaseModel.cause_confirmations` relationship.
- `backend/app/models/__init__.py`: exported `CaseCauseConfirmationModel`.
- `backend/app/schemas/case.py`: `CauseConfirmationRecord`, `SubmitCauseConfirmationRequest`, `CaseCauseConfirmationResponse`.
- `backend/app/db/repository.py`: `get_case_cause_confirmations()`, `append_cause_confirmation_revision()`, updated `load_structured_case()`.
- `backend/app/api/cases.py`: route handler `POST /api/v1/cases/{case_id}/cause-confirmations`.
- `backend/tests/integration/test_cause_confirmation_api.py`: 14 comprehensive API integration tests.
- `backend/tests/integration/test_persistence.py`: repository rollback and mixed revision sequence tests.
- `docs/api/api-spec.md`: documented cause confirmation endpoint, schemas, and semantic invariants.
- `docs/database/erd.md`: documented table 6 and architectural guarantees.
- `backend/README.md`: added cause confirmation endpoint and test runner instructions.
- `.agents/handoff/QUEUE.md`: marked DLK-M3-017 as `implemented`.
- `.agents/handoff/tasks/DLK-M3-017-cause-confirmation-api.md`: updated status and completed report.

### Confirmation API contract

- **Route:** `POST /api/v1/cases/{case_id}/cause-confirmations`
- **Request Body:**
  - `cause_id` (str, required): Candidate cause identifier to confirm.
  - `expected_revision` (int, required, >= 1): Optimistic locking token.
  - `confirmed_by` (str, optional, default "technician"): Technician identifier.
  - `notes` (str | None, optional): Technician rationale or notes.
- **Response (200 OK):** `CaseCauseConfirmationResponse` extending `DurableCaseResponse` with:
  - `current_revision`: Revision number (N+1).
  - `submitted_confirmation`: `CauseConfirmationRecord`.
  - `previous_confirmations`: Full history of confirmed causes.
  - `previous_check_results`: History of troubleshooting checks.
  - `previous_answers`: History of question answers.
  - `confirmed_cause`: Name of confirmed cause.
  - `selected_cause_conclusion`: `CONFIRMED`.
  - `issue_condition`: Preserved (e.g. `UNRESOLVED`).
- **Error Codes:**
  - `404 Not Found`: Case does not exist.
  - `409 Conflict`: Stale revision or replay attempt.
  - `422 Unprocessable Entity`: Unknown cause ID, empty cause ID, invalid revision number (< 1), malformed UUID.
  - `500 Internal Server Error`: Sanitized unexpected server error.

### Persistence/revision decisions

- Monotonic global revision sequence is preserved across question answers, troubleshooting check results, and cause confirmations.
- Table `case_cause_confirmations` enforces unique constraint `uq_case_cause_confirmations_case_id_rev` on `(case_id, resulting_revision_number)` and check constraint `resulting_revision_number > 1`.
- Row-level lock `with_for_update()` on `CaseModel` prevents race conditions during revision generation.

### Issue-condition separation proof

- Verified in `test_cause_confirmation_api.py::test_successful_explicit_cause_confirmation_with_prior_history` and `test_supporting_check_alone_does_not_confirm_cause`:
  - Supporting check increases hypothesis score but does NOT set conclusion to `CONFIRMED`.
  - Explicit confirmation sets cause conclusion to `CONFIRMED`.
  - In all cases, `issue_condition` remains `UNRESOLVED`. Cause confirmation does not invoke recovery verification or issue resolution logic.

### Rollback verification

- Verified in `test_cause_confirmation_api.py::test_cause_confirmation_rollback_on_failure`:
  - A SQLAlchemy `before_commit` event hook raises an injected `RuntimeError` after `append_cause_confirmation_revision()` has flushed pending `CaseCauseConfirmationModel` and `AnalysisRevisionModel` instances to PostgreSQL.
  - In a fresh session, verified that:
    - Failed confirmation record was rolled back (0 confirmations exist).
    - Failed revision snapshot was rolled back (revision count remains 3).
    - Prior question-answer and check-result histories remain intact.
    - Unrelated control case is completely unaffected.
- Verified in `test_persistence.py::test_append_cause_confirmation_revision_rollback_on_failure`:
  - Tested repository transaction rollback on post-flush failure.

### Verification results

- `alembic upgrade head`: Applied revision 0005 cleanly.
- `test_cause_confirmation_api.py`: 14 passed.
- Check-result & semantic suites: 78 passed.
- Question-answer suites: 34 passed.
- Persistence suite: 30 passed.
- Durable case, diagnosis, and health suites: 28 passed.
- Persistence safety suite: 17 passed.
- Full backend suite (`pytest -q`): 226 passed, 0 failed in 18.22s.
- `validate_task.py`: Passed (VALID).
- `git diff --check`: Passed with zero whitespace warnings.

### Limitations and follow-up

- Issue recovery verification, resolution verification, and post-recovery recurrence workflows remain deferred to subsequent milestones.
- Unconfirm / cause revocation is deferred.
- Frontend integration is deferred.

### Proposed commit message

`feat(api): add explicit cause confirmation workflow`
