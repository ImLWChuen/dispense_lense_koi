---
task_id: DLK-M3-013
reviewed_commit: 5e7cb8270762f0e0c06a0c994a0fa424f16f9c2a
decision: changes_requested
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-013

## Decision

Changes requested. The durable check-result workflow needs the two corrections below before acceptance.

## Acceptance evidence

- Inspected the committed API, schemas, migration, ORM, repository changes, semantic correction, and relevant tests/report on backend-database. The working tree was clean before review.
- The ACT03 false directional mapping is removed. Check history participates in bounded reconstruction reads; both append paths use the case lock and global revision sequence. The response is constructed before transaction commit.
- Gemini reports the Phase A gates passing, migration 0004 applied, 20 check API tests, 28 persistence tests, and 206 backend tests passing. These are implementer-reported results; the reviewer did not rerun the database suite.
- Reviewer independently reproduced R1 without database access using the actual request schema and CheckResultHandler. Git committed-diff whitespace inspection passed.

## Findings

### R1 - P1: Reject unfinished checks before they can generate evidence

`backend/app/schemas/case.py:225` accepts every CheckExecutionStatus, including PENDING and IN_PROGRESS. The new route at `backend/app/api/cases.py:551` passes these states to a handler that excludes neither state from evidence generation. A reviewer reproduction with ACT01, IN_PROGRESS, SUPPORTS, blockage_found passed request validation and generated both check_result=ACT01:blockage_found and nozzle_condition=blocked; the summary incorrectly described the check as COMPLETED. The endpoint can therefore persist evidence from an unfinished check.

For this result-submission endpoint, reject PENDING and IN_PROGRESS with 422 before engine execution or persistence. Add API regressions for both states proving no answer/check/observation/revision mutation. If the planner instead chooses to persist unfinished execution states, obtain an explicit semantic scope extension and ensure they generate no evidence; do not silently broaden the existing one-mapping exception.

### R2 - P2: Prove rollback after actual pending writes

`backend/tests/integration/test_check_result_api.py:500` replaces the entire append operation with an immediate exception. `backend/tests/integration/test_persistence.py:1940` removes analysis_revision, triggering validation before a session is acquired or writes begin; the test then explicitly rolls back itself. Neither scenario proves the required rollback after partial writes. This is a verification gap, not a claim that the production rollback implementation is broken.

Exercise the real append/flush in the API request transaction, assert pending check/observation/revision rows actually exist, then inject failure before commit. Query a fresh independent session to verify all new rows are absent, prior snapshots and histories are unchanged, and an unrelated control case survives. Retain a sanitized-500 assertion. Add equivalent repository fault coverage after actual writes if retaining its rollback claim; do not manually perform the rollback being tested.

## Follow-up

Planner should include R1 and R2 in the next bounded correction packet. No new task was generated during this review. The extra canonical-import correction in diagnosis_api.py is reasonable integration maintenance, but was outside the packet's listed paths and should be explicitly acknowledged in the correction report. Correct the report's source example from user_check_result to the actual enum value USER_CHECK_RESULT.

Keep DLK-M3-013 unaccepted and dependent work unreleased. Review artifacts remain local and uncommitted. No push or merge is authorized by this review.
