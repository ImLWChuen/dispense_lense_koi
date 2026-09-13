---
task_id: DLK-M3-010
title: Prove durable API rollback after database writes
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-008]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-010: Durable case verification closeout

## Objective

Resolve R1 in the DLK-M3-009 review with real PostgreSQL API rollback evidence and accurate documentation.

## Current evidence

DLK-M3-009 is implemented at 468ee3d311db7bcea114f580e28539602a91967b with changes requested. Its presence is required, not its acceptance. Read its task and review. The current failure test mocks save_initial_case before any write and checks absence only by description. The route already includes rollback; this task does not assume a production defect.

## Requirements

- Exercise real repository writes through POST /api/v1/cases, then induce a failure after flush and before commit. Prove the test reached actual writes in the request transaction.
- Capture the actual generated case ID. Verify absence of case, observations and revision from a fresh independent session after the failed response; verify an unrelated control case remains intact.
- Verify the API returns a sanitized 500 without exposing deliberately distinctive synthetic secrets in the injected exception.
- Strengthen happy-path verification to compare complete POST/GET semantic state, full observation metadata and full stored diagnosis snapshot, rather than selected result fields alone.
- Document and test the current inconclusive-diagnosis behavior: valid input that yields no identified defect/revision is rejected with 422 by the durable endpoint and produces no stored case, while the stateless endpoint returns its inconclusive result. This records current behavior, not approval of a permanent product restriction.
- Correct misleading verification/transaction descriptions in the Task 009 report, retaining its historical results as implementer-reported. Record new exact commands/outcomes in this task.

## Interfaces and data contracts

No product behavior, engine, schema or migration changes. Retain current API contracts for this bounded correction. Durable storage for inconclusive diagnoses remains a planner decision; never invent engine evidence or a revision to bypass repository validation.

## Allowed paths

- backend/tests/integration/test_case_api.py
- docs/api/api-spec.md
- .agents/handoff/tasks/DLK-M3-009-durable-case-api.md (report accuracy only)
- .agents/handoff/tasks/DLK-M3-010-durable-case-verification-closeout.md
- .agents/handoff/reviews/DLK-M3-009-review.md (include unchanged)
- .agents/handoff/QUEUE.md

## Prohibited scope

No application implementation, schema, migrations, dependencies, frontend, engine, follow-up workflows, database resets or remote Git operations.

## Implementation guidance

1. Confirm branch/baseline and preserve review artifacts. Mark this task in_progress.
2. Use a bounded wrapper or fault seam that calls the real repository on the request's session, verifies flushed rows and raises before commit. Do not replace the whole operation with an immediate error.
3. Isolate tests by actual generated IDs. Preserve unrelated database records and clean only records created by these tests.
4. Add complete response/snapshot comparisons and explicit inconclusive-result coverage/documentation.
5. Run focused and full checks on the verified local PostgreSQL destination. Report blocked if required database checks cannot run.
6. Complete the report and commit the scoped work locally.

## Acceptance criteria

- [x] Failure is injected after real flushed writes, before successful commit.
- [x] A fresh session verifies no rows in all three tables for the failed case ID, and the control case survives unchanged.
- [x] Failure response is sanitized; full successful POST/GET and stored snapshot parity is verified.
- [x] Current inconclusive-result limitation is explicitly tested and documented without changing behavior.
- [x] Focused and full backend suites pass against real local PostgreSQL.
- [x] Reports describe actual implementation and verification; only scoped paths change.

## Verification

From backend/ using the existing verified local PostgreSQL DATABASE_URL and schema:

1. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_case_api.py`
2. `.\.venv\Scripts\python.exe -m pytest -q`

From repository root:

3. `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-010-durable-case-verification-closeout.md`
4. `git diff --check`

## Planner decision boundaries

Return before any application fix, API behavior change, schema change or durable-inconclusive-case design. If tests uncover a real failure, report the exact evidence; do not weaken assertions to obtain a pass.

## Git instructions

One atomic local commit after required checks pass. Include pending review/queue/task artifacts. Do not push, merge, rebase or create a PR.

Proposed commit: `test(api): verify durable case rollback and response parity`

## Implementation report

### Summary

Resolved review finding R1 on DLK-M3-009 by adding real PostgreSQL transaction rollback verification after actual database writes and flushes, proving that failed POST requests clean up all uncommitted rows across `cases`, `case_observations`, and `case_analysis_revisions` without corrupting unrelated control data. Strengthened the happy-path test to assert full semantic state parity between POST and GET responses as well as complete relational snapshot equality in PostgreSQL. Added explicit test coverage and documentation for the inconclusive-diagnosis behavior difference between stateless and durable endpoints. Corrected transaction and migration naming accuracy in the DLK-M3-009 report.

### Files changed

- `backend/tests/integration/test_case_api.py`:
  - Strengthened `test_create_and_retrieve_durable_case_happy_path` with complete dictionary parity (`get_data == post_data`), relational model field comparisons, full observation metadata checks, and stored `result_snapshot` validation.
  - Added `test_rollback_after_real_flushed_writes_leaves_no_partial_case`, proving that rows flushed to the active transaction roll back cleanly upon failure, leaving 0 records across all 3 tables for the failed case ID, while preserving an unrelated control case and sanitizing synthetic credentials in error output.
  - Renamed immediate error test to `test_immediate_repository_failure_handles_error_safely`.
  - Added `test_inconclusive_diagnosis_behavior_difference` testing that inputs with no defect category are accepted statelessly (200 OK, defect=None, analysis_revision=None) and rejected durably (422 Unprocessable Entity) without database writes.
- `docs/api/api-spec.md`:
  - Updated Section 3 comparison table and Section 3.1 with inconclusive diagnosis limitation documentation (HTTP 422).
  - Added 422 inconclusive diagnosis and 500 durable case failure examples to the Error Handling section.
- `.agents/handoff/tasks/DLK-M3-009-durable-case-api.md`:
  - Corrected transaction description to match FastAPI dependency and explicit session commit/rollback, corrected migration revision name to `0002_widen_unrestricted_strings`, and removed trailing blank line at EOF.
- `.agents/handoff/tasks/DLK-M3-010-durable-case-verification-closeout.md`:
  - Checked off all acceptance criteria and completed implementation report; status updated to `implemented`.
- `.agents/handoff/QUEUE.md`:
  - Updated task `DLK-M3-010` status to `implemented`.

### Decisions made

- Used a fault injection wrapper on `CaseRepository.save_initial_case` that executes real model writes and `session.flush()`, verifies that rows exist in the request transaction via the active session (`self._session`), and then raises a synthetic exception containing a distinct synthetic secret token before `session.commit()`.
- Verified rollback from a fresh independent session checking `cases`, `case_observations`, and `case_analysis_revisions` by exact case ID.
- Established an unrelated control case prior to failure injection to verify that transaction rollback does not affect unrelated records.
- Preserved current application logic and contracts exactly without adding or modifying production endpoints or schemas.

### Verification results

1. `tests/integration/test_case_api.py`: 15 passed in 1.89s (including new real flushed writes rollback proof, immediate error safety, full POST/GET snapshot parity, and inconclusive diagnosis behavior difference).
2. Complete backend test suite (`pytest -q`): 67 passed, 2 warnings in 2.69s.
3. Database-free isolation check: Stateless diagnosis and health tests pass without `DATABASE_URL` set (13 passed in 0.92s).
4. Task packet validation: `validate_task.py` passed for DLK-M3-010.
5. `git diff --check`: passed with 0 warnings.

### Limitations and follow-up

- Inconclusive diagnosis support for durable cases remains deferred to future contract planning; the endpoint currently rejects cases lacking an initial analysis revision with 422.
- Revision 2+ workflows, troubleshooting check result submission, and question answer endpoints remain deferred to subsequent milestones.

### Proposed commit message

`test(api): verify durable case rollback and response parity`

