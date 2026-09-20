---
task_id: DLK-M3-014
title: Close troubleshooting-check result safety and rollback verification
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-013]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-014: Troubleshooting-check result closeout

## Objective

Close the two findings blocking acceptance of DLK-M3-013 without redesigning the durable troubleshooting-check workflow:

1. reject unfinished `PENDING` and `IN_PROGRESS` result submissions before diagnostic evidence generation or persistence;
2. prove transaction rollback after real pending/flushed database writes, rather than only proving failures that occur before writes begin.

Preserve the accepted parts of DLK-M3-013, including the ACT03 correction, durable check history, reconstruction, global revision sequencing, stale-revision protection, and separation of check result, cause confirmation, and issue resolution.

## Current evidence

DLK-M3-013 was reviewed at commit:

`5e7cb8270762f0e0c06a0c994a0fa424f16f9c2a`

The review returned `changes_requested`.

### R1 - unfinished checks can generate evidence

`PENDING` and `IN_PROGRESS` currently pass request validation. An evidence-producing payload can therefore reach `CheckResultHandler`, produce observations, and potentially persist a new revision even though the check is unfinished.

### R2 - rollback is not proven after actual writes

Existing failure tests inject exceptions before real pending writes exist or manually roll back the transaction being tested. They therefore do not prove atomic rollback after flushed check/observation/revision writes.

The review also asks the correction report to:

- acknowledge the previously introduced canonical-import maintenance in `diagnosis_api.py`;
- use the actual provenance enum spelling `USER_CHECK_RESULT`.

## Requirements

### R1 - reject unfinished results

`POST /api/v1/cases/{case_id}/check-results` is a result-submission endpoint.

Reject these execution states with `422 Unprocessable Entity` before engine/check handler execution and before persistence:

- `PENDING`
- `IN_PROGRESS`

The rejected request must not:

- append check-result history;
- append `CHECK_RESULT` evidence;
- append derived observations;
- alter scores/evidence;
- append an analysis revision;
- change current revision;
- mutate any other durable case state.

Do not reinterpret unfinished states as completed results.

Preserve existing semantics for valid result states and do not change Member 2's check mappings, evidence rules, scoring, explicit cause confirmation, or issue-resolution behavior.

If the shared schema is used outside this endpoint, prefer the smallest endpoint-specific validation that enforces this result-submission policy without breaking legitimate internal/domain representations.

### Required R1 tests

Add API regressions for both `PENDING` and `IN_PROGRESS`.

Each must prove:

- response is `422`;
- no check-history mutation;
- no observation mutation;
- no revision mutation;
- current revision remains unchanged;
- prior stored snapshots remain unchanged.

Use an otherwise-valid adversarial payload that would create evidence if it reached the handler, so the test proves unfinished-state rejection rather than failing for an unrelated reason.

### R2 - rollback after real pending writes

Exercise the real production write path and prove rollback after writes have actually been flushed/pending in the transaction.

The proof must not rely on:

- replacing the whole append operation with an immediate exception;
- validation failure before a session/write begins;
- manually calling `rollback()` as the rollback mechanism under test.

### API transaction rollback proof

Through the real API request transaction:

1. create a durable case with known baseline state;
2. submit a valid evidence-producing check result;
3. allow the real append path to create/flush:
   - check-result history;
   - generated observation(s);
   - new analysis revision;
4. assert inside the transaction that those pending rows/state exist;
5. inject failure after flush but before successful commit;
6. let the production transaction boundary perform rollback naturally;
7. assert the HTTP response is a sanitized `500`;
8. open a fresh independent session;
9. verify all attempted new rows are absent;
10. verify prior case snapshots/history are unchanged;
11. verify an unrelated control case remains unchanged.

Prefer a test-only SQLAlchemy/session event or equivalent commit-boundary failure injection. Do not add a production failure switch merely for tests.

### Repository rollback proof

If the implementation report retains a repository-level rollback/atomicity claim, add equivalent repository coverage after actual writes/flushes. Do not manually perform the rollback being tested.

### Report/audit cleanup

Update the implementation reporting so it:

- explicitly acknowledges the prior `diagnosis_api.py` canonical-import maintenance as reasonable integration maintenance that was outside DLK-M3-013's originally listed paths;
- does not imply that scope deviation was originally authorized;
- uses `USER_CHECK_RESULT`, not `user_check_result`, as the provenance enum example;
- distinguishes implementer-run verification from reviewer-replayed verification accurately.

Do not make unrelated `diagnosis_api.py` changes.

### Contract preservation

No product API redesign is authorized.

Preserve:

- check-result route and success response;
- stale-revision `409`;
- missing-case behavior;
- check/action/outcome validation;
- revision sequencing;
- durable case/question-answer APIs;
- stateless diagnosis API.

The intended client-visible change is only:

`PENDING` / `IN_PROGRESS` result submissions -> `422`.

## Interfaces and data contracts

- Preserve the existing `POST /api/v1/cases/{case_id}/check-results` request and response models, status behavior, durable history, and revision contract.
- Add only the endpoint policy that `PENDING` and `IN_PROGRESS` execution states return `422` without mutation.
- Do not change the database schema, migration history, successful response shape, diagnostic domain models, or evidence semantics.
- Failure injection used to prove rollback must remain test-only and must exercise the existing production transaction boundary.

## Allowed paths

- `backend/app/schemas/case.py`
- `backend/app/api/cases.py` only if endpoint-specific validation is required there
- `backend/tests/integration/test_check_result_api.py`
- `backend/tests/integration/test_persistence.py`
- existing check-result test fixtures/helpers only when required for bounded failure injection
- `docs/api/api-spec.md`
- `backend/README.md` only if unfinished-state validation is documented there
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/NEXT-STEPS.md` only for closeout progression
- `.agents/handoff/reviews/DLK-M3-013-review.md` (include unchanged)
- `.agents/handoff/tasks/DLK-M3-013-troubleshooting-check-result-api.md` only for narrow implementation-report corrections
- `.agents/handoff/tasks/DLK-M3-014-check-result-closeout.md`

Return to the planner before editing outside this scope.

## Prohibited scope

Do not change:

- database schema or migrations;
- dependencies;
- Member 2 action/outcome mappings;
- evidence rules;
- scoring;
- question-answer semantics;
- action-planner logic;
- cause-confirmation semantics;
- issue-resolution semantics;
- PostgreSQL destination-safety policy.

Do not add:

- cause-confirmation API;
- recovery API;
- report generation;
- authentication;
- frontend work;
- LLM/CV;
- generic workflow CRUD.

## Implementation guidance

1. Confirm DLK-M3-013 is the reviewed implementation and DLK-M3-014 is the only ready correction task.
2. Add the smallest endpoint-specific unfinished-state validation and its two no-mutation API regressions.
3. Replace the pre-write failure tests with a test-only failure seam that observes real flushed rows and fails before commit.
4. Verify rollback from a fresh independent session and preserve an unrelated control case.
5. Make only the authorized DLK-M3-013 report corrections, then run the focused and complete verification commands.
6. Complete the implementation report, inspect the staged diff, and create one atomic local commit without remote Git operations.

## Acceptance criteria

### R1

- [x] `PENDING` returns `422`.
- [x] `IN_PROGRESS` returns `422`.
- [x] Both are rejected before evidence generation.
- [x] No check history, observations, revisions, or current-revision mutation occurs.
- [x] Tests use otherwise-valid evidence-producing payloads.
- [x] Existing valid result states retain prior behavior.

### R2

- [x] Rollback test reaches real pending/flushed check rows.
- [x] Pending generated observation(s) exist before injected failure.
- [x] Pending new revision exists before injected failure.
- [x] Failure occurs after flush and before successful commit.
- [x] Production transaction management performs rollback naturally.
- [x] Fresh independent session finds no attempted new rows.
- [x] Prior state is unchanged.
- [x] Unrelated control case remains intact.
- [x] HTTP `500` is sanitized.
- [x] Repository post-write rollback is also proven if repository atomicity remains explicitly claimed.

### Regression

- [x] ACT03 semantic correction remains intact.
- [x] Supporting checks do not auto-confirm causes.
- [x] Check results do not auto-resolve issues.
- [x] Check-result API happy path passes.
- [x] Stale revision remains `409`.
- [x] Question-answer workflow passes.
- [x] Durable case/diagnosis/health APIs pass.
- [x] Persistence tests pass.
- [x] Semantic verification passes.
- [x] Full backend suite passes.
- [x] No migration/schema change.
- [x] Only authorized files change.
- [x] No remote Git operation occurs.

### Audit

- [x] Prior `diagnosis_api.py` maintenance is explicitly acknowledged.
- [x] `USER_CHECK_RESULT` is used correctly.
- [x] Verification claims correctly identify implementer vs reviewer execution.

## Verification

Use the accepted verified local PostgreSQL test database.

From `backend/`, run at minimum:

1. semantic verification suite;
2. CheckResultHandler focused suite;
3. check-result diagnosis/revision integration suite;
4. Phase 9-11 suite;
5. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_check_result_api.py`
6. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_persistence.py`
7. question-answer API/revision suites;
8. durable case + diagnosis + health API suites;
9. persistence-safety suite;
10. `.\.venv\Scripts\python.exe -m pytest -q`

Inspect OpenAPI and verify existing routes remain unchanged and unfinished result-state rejection is documented consistently.

From repository root:

11. `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-014-check-result-closeout.md`
12. `git diff --check`
13. inspect `git status`, staged names, and staged diff before commit.

If real PostgreSQL verification cannot run, mark the task `blocked`.

## Planner decision boundaries

Return to the planner before:

- allowing unfinished result states to persist;
- changing check semantics;
- changing schema/migrations;
- adding production failure-injection hooks;
- changing cause confirmation or issue resolution;
- changing successful response shapes;
- adding dependencies;
- starting the next milestone.

## Git instructions

After all criteria pass:

- complete the DLK-M3-014 implementation report;
- make only the narrow report corrections allowed in DLK-M3-013;
- mark DLK-M3-014 and `QUEUE.md` `implemented`;
- inspect staged files/diff;
- create one atomic local commit.

Proposed commit message:

`fix(api): close out troubleshooting check workflow`

Do not push, merge, rebase, create/update a PR, or modify `main`.

## Implementation report

### Summary

Successfully closed both findings from the DLK-M3-013 review (`changes_requested`) without altering database schemas, migrations, or Member 2 diagnostic semantics:
1. Enforced rejection of unfinished execution statuses (`PENDING` and `IN_PROGRESS`) with `HTTP 422 Unprocessable Entity` in `SubmitCheckResultRequest` schema validation and endpoint defense-in-depth before diagnostic evidence generation or database persistence.
2. Proved transaction rollback after actual pending/flushed database writes in both the HTTP API endpoint (`test_check_result_api.py`) and repository transaction layer (`test_persistence.py`), verifying complete rollback, sanitized HTTP 500 error reporting, and isolation of unrelated control cases via fresh independent sessions without manual rollback calls.
3. Updated audit reports: explicitly acknowledged prior `diagnosis_api.py` canonical-import maintenance as unprescribed integration maintenance, standardized enum spelling to `EvidenceSource.USER_CHECK_RESULT`, and clarified implementer-executed verification.

### Files changed

- `backend/app/schemas/case.py`: Added field and model validation to `SubmitCheckResultRequest` rejecting `CheckExecutionStatus.PENDING` and `CheckExecutionStatus.IN_PROGRESS` with descriptive `ValueError`.
- `backend/app/api/cases.py`: Added defense-in-depth check in `submit_case_check_result` explicitly rejecting `PENDING` and `IN_PROGRESS` with `HTTPException(422)` before domain check construction, handler execution, engine evaluation, or persistence.
- `docs/api/api-spec.md`: Documented unfinished execution status rejection in the lifecycle contract, request schema description, and validation rules for `POST /api/v1/cases/{case_id}/check-results`.
- `backend/tests/integration/test_check_result_api.py`:
  - Added `test_unfinished_execution_status_rejected_with_422_and_no_mutation` parametrized across `PENDING` and `IN_PROGRESS` with otherwise-valid evidence-producing payloads, asserting HTTP 422 and zero mutation of check results, observations, or revisions.
  - Rewrote `test_induced_persistence_failure_returns_sanitized_500_and_rolls_back` to assert flushed check result, observation, and revision rows exist in PostgreSQL via a test-only `before_commit` event hook, raise an unhandled exception before commit, let production rollback execute naturally, verify sanitized HTTP 500 without leaking file paths, and verify complete state restoration and control case isolation from a fresh independent session.
- `backend/tests/integration/test_persistence.py`:
  - Rewrote `test_append_check_result_revision_rollback_on_failure` to assert flushed rows exist via `before_commit`, trigger commit failure, verify natural repository rollback without manual rollback calls, and verify control case isolation from a fresh independent session.
- `.agents/handoff/tasks/DLK-M3-013-troubleshooting-check-result-api.md`: Corrected audit points per review (acknowledged `diagnosis_api.py` canonical-import maintenance, updated provenance enum to `EvidenceSource.USER_CHECK_RESULT`, and noted implementer execution of test suites).
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-014 status to `implemented`.
- `.agents/handoff/tasks/DLK-M3-014-check-result-closeout.md`: Recorded implementation report and marked `implemented`.

### R1 unfinished-state correction

- `POST /api/v1/cases/{case_id}/check-results` is strictly a result submission endpoint for checks that have produced a finding or terminated non-execution.
- `PENDING` and `IN_PROGRESS` represent unexecuted or incomplete activities and cannot produce valid diagnostic evidence.
- Rejection occurs at both the Pydantic schema validation layer (`@field_validator("execution_status")` and `@model_validator`) and route handler guard (`submit_case_check_result`), returning HTTP 422 before `CheckResultHandler.handle` or `engine.submit_check_result` is invoked.
- Regression tests with adversarial payloads (`ACT01`, `SUPPORTS`, `blockage_found`) confirmed that zero observations, zero check records, and zero revisions are persisted, and the case remains at revision 1.

### R2 post-write rollback proof

- Both the API test (`test_induced_persistence_failure_returns_sanitized_500_and_rolls_back`) and repository test (`test_append_check_result_revision_rollback_on_failure`) now prove atomic rollback after real flushed writes:
  1. Creates an unrelated control case (Case A) and target case (Case B).
  2. Executes real evidence-producing check result (`ACT01`, `COMPLETED`, `SUPPORTS`, `blockage_found`).
  3. Real append logic flushes `CaseCheckResultModel`, `ObservationModel`s (with `first_seen_revision = 2`), and `AnalysisRevisionModel` (`revision_number = 2`) to PostgreSQL.
  4. Test-only SQLAlchemy `before_commit` event listener asserts that each of these rows exists in the pending transaction.
  5. The listener injects a `RuntimeError` containing sensitive path details before the commit is finalized.
  6. The production transaction boundary (`except Exception:` in route handler or repository) catches the failure, invokes `session.rollback()`, and raises the sanitized error.
  7. Test verifies HTTP 500 contains sanitized detail and excludes sensitive file paths.
  8. A fresh independent session confirms all revision 2 rows are absent, target case is at revision 1 with original observations, and control case is untouched.

### Prior scope-maintenance acknowledgement

- The prior update to `backend/app/schemas/diagnosis_api.py` in DLK-M3-013 normalized imports from `from backend.app...` to `from app...`. This was reasonable integration maintenance to resolve a Pydantic duplicate class identity collision during test execution, but was outside DLK-M3-013's originally listed allowed paths and is explicitly acknowledged as unprescribed maintenance.
- Provenance enum spelling in reports has been corrected to `EvidenceSource.USER_CHECK_RESULT`.

### Verification results (implementer execution)

All suites were executed locally against real PostgreSQL 16 Alpine:

1. Semantic verification suite (`tests/unit/test_semantic_verification.py`): 36 passed
2. CheckResultHandler focused suite (`tests/unit/test_check_result_handler.py`): 10 passed
3. Check-result diagnosis/revision integration suite (`tests/integration/test_check_result_diagnosis_revision.py`): 8 passed
4. Phase 9-11 suite (`tests/test_phases_9_11.py`): 8 passed
5. Check-result API integration suite (`tests/integration/test_check_result_api.py`): 22 passed
6. Persistence integration suite (`tests/integration/test_persistence.py`): 28 passed
7. Question-answer API/revision suites (`tests/integration/test_question_answer_api.py`): 19 passed
8. Durable case + diagnosis + health API suites (`tests/integration/test_case_api.py`, `test_diagnosis_api.py`, `test_health_api.py`): 37 passed
9. Persistence-safety suite (`tests/unit/test_persistence_safety.py`): 8 passed
10. Full backend test suite (`pytest -q`): **208 passed, 0 failed**, 12 warnings in 12.01s.
11. Task validation (`validate_task.py`): **`VALID`**.
12. Whitespace check (`git diff --check`): 0 whitespace errors.

### Limitations and follow-up

- Cause confirmation and issue recovery remain decoupled and are deferred to later tasks (`DLK-M3-015`+).
- Remote Git operations (push, PR, merge) remain forbidden as per `PROJECT.md`.

### Proposed commit message

`fix(api): close out troubleshooting check workflow`
