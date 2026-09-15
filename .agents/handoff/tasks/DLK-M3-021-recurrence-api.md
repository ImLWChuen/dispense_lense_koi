---
task_id: DLK-M3-021
title: Add durable resolved-issue recurrence reporting workflow
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-020]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-021: Durable resolved-issue recurrence reporting workflow

## Objective

Add explicit reporting that a previously verified `RESOLVED` issue has recurred.

Implement exactly:

`POST /api/v1/cases/{case_id}/recurrences`

The endpoint must:

1. load/lock the durable case;
2. verify `expected_revision`;
3. require current `issue_condition == RESOLVED`;
4. reconstruct the current `StructuredCase`;
5. use the existing state-manager transition to `RECURRED`;
6. atomically persist the lifecycle event and Revision N+1;
7. return committed updated state.

Do not automatically start a new recovery cycle and do not generate a report.

## Current evidence

DLK-M3-020 is accepted at:

`78a9a2bbf3a14329a26b42b333cdce492c4eee96`

The accepted lifecycle already provides recovery action, pending-verification enforcement, pass/fail verification, sanitized internal errors, full rollback-history proof, and global revision sequencing.

## Requirements

Recurrence is an issue-condition event only.

Reporting recurrence must not automatically:

- change cause ranking or evidence;
- confirm/unconfirm a cause;
- enter `RECOVERY_PENDING_VERIFICATION`;
- resolve the issue;
- rewrite earlier recovery events.

Preserve:

`cause conclusion != issue recurrence`

## Interfaces and data contracts

At minimum:

- `expected_revision`
- `recurrence_details`

Optional:

- `reported_by` with max length 64

Store unrestricted recurrence details faithfully using the existing lifecycle-event storage. Prefer no migration if the current lifecycle schema can already represent recurrence.

The client must not submit an arbitrary target state.

## State precondition

This endpoint is valid only from `RESOLVED`.

Using the current revision:

- `UNRESOLVED` -> recurrence => `422`
- `RECOVERY_PENDING_VERIFICATION` -> recurrence => `422`
- `RECURRED` -> recurrence => `422`
- `RESOLVED` -> may proceed

This is an endpoint-specific precondition. Do not modify the general state-transition map.

After prevalidation, still invoke the existing state manager for the actual transition.

## Status contract

- `200` success
- `404` missing case
- `409` stale revision
- `422` invalid source state / malformed request
- `500` unexpected internal failure, sanitized

Unexpected state-manager failures during a legal transition must not expose raw exception text.

## Persistence and revision rules

Reuse the existing lifecycle-event table/model and global revision sequence if it can represent recurrence faithfully.

One successful recurrence must atomically append:

- one recurrence lifecycle event;
- one immutable Revision N+1.

Prior revisions remain unchanged.

Replay with a consumed `expected_revision` must return `409` and append nothing.

## Cause-state invariant

A recurrence must leave existing cause conclusions unchanged.

Explicitly test that:

- a previously confirmed cause remains confirmed;
- an unconfirmed cause does not become confirmed merely because recurrence was reported.

If current domain behavior contradicts this, stop and return to the planner.

## Rollback proof

Add a real post-write rollback scenario:

1. create a realistic case with prior question answer, check result, confirmation, recovery action, and successful recovery verification (`RESOLVED`);
2. allow recurrence event + new revision to be flushed/pending;
3. inject failure before commit;
4. let production transaction handling roll back;
5. verify in a fresh independent session:
   - attempted recurrence event absent;
   - attempted revision absent;
   - issue remains `RESOLVED`;
   - prior question/check/confirmation/lifecycle history unchanged;
   - prior revision snapshots unchanged;
   - unrelated control case unchanged.

Do not manually perform the rollback under test.

## Implementation guidance

Implement the request, state precondition, persistence/revision rules, cause-state invariant, and rollback proof specified above within the allowed paths. Run the required scenarios and verification before completing the implementation report.

## Allowed paths

- `backend/app/api/cases.py`
- `backend/app/schemas/case.py`
- `backend/app/db/repository.py` only if minimal recurrence support is needed
- `backend/app/models/case.py` only if existing lifecycle-event typing needs a non-schema semantic extension
- `backend/tests/integration/test_recurrence_api.py`
- `backend/tests/integration/test_persistence.py`
- `backend/tests/case_snapshot_helper.py` if bounded helper support is needed
- `docs/api/api-spec.md`
- `docs/database/erd.md` only if documentation needs recurrence notation
- `backend/README.md` only for small workflow documentation
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/NEXT-STEPS.md`
- `.agents/handoff/reviews/DLK-M3-020-review.md` unchanged
- `.agents/handoff/tasks/DLK-M3-021-recurrence-api.md`

Return to the planner before editing outside this scope.

## Prohibited scope

Do not:

- alter state-manager semantics;
- add a generic issue-state endpoint;
- auto-start recovery;
- change cause conclusions;
- add recurrence update/delete;
- add report/PDF generation;
- add frontend/auth/LLM/CV/retrieval work;
- add unrelated dependencies;
- weaken PostgreSQL safety.

No migration is authorized unless the existing lifecycle schema cannot faithfully store recurrence; return to the planner first.

## Acceptance criteria

- [x] Only `RESOLVED` may report recurrence.
- [x] Success returns `200`.
- [x] Issue becomes `RECURRED`.
- [x] Exactly one lifecycle event is appended.
- [x] Exactly one immutable revision is appended.
- [x] Cause conclusions remain unchanged.
- [x] `UNRESOLVED`, `RECOVERY_PENDING_VERIFICATION`, and `RECURRED` source states return `422` using current revisions.
- [x] Invalid-state requests create no mutation.
- [x] stale/replayed revision returns `409`.
- [x] unexpected internal transition failure returns sanitized `500` with zero mutation.
- [x] rollback after real pending writes preserves complete prior durable state.
- [x] global revision sequence continues without reset/collision.
- [x] all existing workflow regressions pass.
- [x] no remote Git operation occurs.

## Required scenarios

1. Resolved -> recurrence success.
2. Recurrence on a resolved case with no confirmed cause; no cause becomes confirmed.
3. Invalid source-state matrix for `UNRESOLVED`, `RECOVERY_PENDING_VERIFICATION`, `RECURRED`.
4. Stale/replay conflict.
5. Missing case.
6. Injected sensitive-marker internal `ValueError` -> sanitized `500`.
7. Post-write rollback.
8. Mixed revision sequence:
   R1 initial -> R2 answer -> R3 check -> R4 confirmation -> R5 recovery action -> R6 verification -> R7 recurrence.

## Documentation

Update `docs/api/api-spec.md` with the route, request, `200/404/409/422/500`, optimistic concurrency, and explicit statements that recurrence:

- is accepted only from `RESOLVED`;
- does not alter cause confirmation;
- does not automatically start a new recovery cycle.

## Verification

Using verified local PostgreSQL:

From `backend/` run:

1. `./.venv/Scripts/python.exe -m pytest -q tests/integration/test_recurrence_api.py`
2. persistence/rollback suite
3. recovery verification suite
4. cause-confirmation suite
5. check-result + semantic suites
6. question-answer suites
7. durable case + diagnosis + health suites
8. persistence-safety suite
9. full backend suite: `./.venv/Scripts/python.exe -m pytest -q`
10. inspect OpenAPI

From repo root:

11. validate task packet
12. `git diff --check`
13. inspect status, staged files, staged diff

If real PostgreSQL verification cannot run, mark the task `blocked`.

## Planner decision boundaries

Return to the planner before expanding the allowed paths or prohibited scope, changing existing domain semantics, or redesigning the existing case/revision contracts.

## Git instructions

After all criteria pass:

- complete implementation report;
- mark DLK-M3-021 and queue `implemented`;
- create one atomic local commit:

`feat(api): add issue recurrence workflow`

Do not push, merge, rebase, create/update a PR, or modify `main`.

## Implementation report

### Summary

- Unblocked from review `blocked` by fixing trailing EOF whitespace across five tracked files (`backend/app/api/cases.py`, `backend/app/db/repository.py`, `backend/app/schemas/case.py`, `backend/tests/integration/test_persistence.py`, `docs/api/api-spec.md`), correcting the documented interpreter path to `./.venv/Scripts/python.exe`, and completing full PostgreSQL verification against the active local container.
- Implemented `POST /api/v1/cases/{case_id}/recurrences` to allow durable reporting of recurrence for an issue previously verified as `RESOLVED`.
- Strictly enforces the `issue_condition == RESOLVED` precondition: requests from `UNRESOLVED`, `RECOVERY_PENDING_VERIFICATION`, or `RECURRED` return HTTP `422` with zero database mutation.
- Enforces optimistic concurrency by verifying `expected_revision == current_revision`, rejecting stale or replayed requests with HTTP `409` and zero mutation.
- Integrates with domain `StateManager.record_recurrence(current_case)` to transition issue condition to `RECURRED` without modifying any cause conclusions, rankings, or evidence.
- Preserves cause invariant: confirmed causes remain confirmed, and unconfirmed causes do not become confirmed.
- Does not trigger an automatic recovery cycle or modify earlier recovery verification events.
- Reuses existing `CaseLifecycleEventModel` with `event_type="RECURRENCE"`, `verification_passed=None`, `details=request.recurrence_details`, and `reported_by=request.reported_by`. Appends immutable Revision N+1 in an atomic locked session.
- Sanitizes unexpected domain or internal `ValueError`s into generic HTTP `500` without leaking internal diagnostic strings or system details.
- Validated post-write rollback: failure injected at `before_commit` rolls back pending database writes, preserving complete target case baseline and unrelated control cases.

### Files changed

- `backend/app/schemas/case.py`: Added `SubmitRecurrenceRequest` (validating `expected_revision >= 1`, non-empty `recurrence_details`, optional `reported_by` max 64 chars, and forbidding extra attributes) and `CaseRecurrenceResponse` schema models.
- `backend/app/api/cases.py`: Implemented `submit_case_recurrence` route handler with UUID validation, `RESOLVED` precondition check, optimistic revision checking, domain state transition, locked repository append, pre-commit response serialization, and sanitized HTTP 500 handling.
- `backend/app/db/repository.py`: Added `append_recurrence_event` method wrapping atomic `append_lifecycle_event` with `event_type="RECURRENCE"`, `verification_passed=None`, `details`, and `reported_by`.
- `backend/tests/integration/test_recurrence_api.py`: Added integration test suite with 9 scenarios testing happy path, unconfirmed cause preservation, invalid source states (422), stale revision conflict (409), input validation and missing case (404/422), internal error sanitization (500), post-write rollback before commit, and 7-revision mixed sequence.
- `backend/tests/integration/test_persistence.py`: Added persistence-level recurrence integration tests verifying locked atomic persistence, revision monotonicity, and rollback guarantees.
- `docs/api/api-spec.md`: Documented `POST /api/v1/cases/{case_id}/recurrences` with request/response schemas, status codes (`200`, `404`, `409`, `422`, `500`), optimistic concurrency, and domain semantics.
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-021 status to `implemented`.
- `.agents/handoff/tasks/DLK-M3-021-recurrence-api.md`: Updated frontmatter status to `implemented`, checked all criteria, and recorded complete implementation report.

### Recurrence API contract

- **Route**: `POST /api/v1/cases/{case_id}/recurrences`
- **Request Body**:
  - `expected_revision` (integer, ge=1, required): Revision expected prior to recurrence.
  - `recurrence_details` (string, min_length=1, required): Operator description of recurrence observations.
  - `reported_by` (string, max_length=64, optional): Identifier of the operator reporting recurrence.
- **Precondition**: Case must exist and have current `issue_condition == RESOLVED`.
- **Response**: `200 OK` returning `CaseRecurrenceResponse`:
  - `case_id`: UUID string.
  - `issue_condition`: `"RECURRED"`.
  - `lifecycle_event`: Event representation with `id`, `event_type="RECURRENCE"`, `verification_passed=None`, `details`, `reported_by`, `created_at`.
  - `revision`: Updated revision metadata (`revision_number`, `source_event_type="RECURRENCE"`, `source_event_id`).
  - `diagnosis`: Full current diagnosis projection.
- **Error Codes**:
  - `404 Not Found`: Case does not exist.
  - `409 Conflict`: Stale `expected_revision` or replay.
  - `422 Unprocessable Content`: Illegal source condition (`UNRESOLVED`, `RECOVERY_PENDING_VERIFICATION`, `RECURRED`), malformed UUID, or invalid request payload.
  - `500 Internal Server Error`: Sanitized internal exception response.

### Lifecycle/revision decisions

- Reused existing `CaseLifecycleEventModel` table with `event_type="RECURRENCE"` and `verification_passed=None`. No database migration required.
- Reconstructed `StructuredCase` from durable history and passed it to `StateManager.record_recurrence()`, ensuring consistency with domain transition rules.
- Atomic append operation generates Revision N+1 linked to the new recurrence lifecycle event. All prior revision snapshots remain strictly immutable.
- Explicitly maintained separation of concerns: reporting recurrence updates issue condition only; it does not unconfirm or confirm causes, modify cause rankings, or generate automated recovery actions.

### Rollback verification

- Implemented in `test_post_write_rollback_preserves_target_and_control` using SQLAlchemy `before_commit` hook after `append_recurrence_event` has flushed pending writes to the database.
- Failure injection verified that production transaction handling safely issues `session.rollback()`.
- Verified in an independent database session that:
  1. The flushed recurrence event is completely absent from `case_lifecycle_events`.
  2. The flushed revision is completely absent from `analysis_revisions`.
  3. Case `issue_condition` remains `RESOLVED`.
  4. Prior question answers, check results, cause confirmations, and lifecycle events are identical to the pre-test snapshot.
  5. Prior revision snapshots R1 through R6 remain unchanged.
  6. An unrelated control case remains completely intact and unaffected.

### Verification results

The task was unblocked from review `blocked` by fixing EOF whitespace, correcting the documented interpreter path to `./.venv/Scripts/python.exe`, and completing PostgreSQL verification against the active local PostgreSQL 16 container (`dispenselens-postgres`).

All verification test suites were executed against the real PostgreSQL database from `backend/` using `./.venv/Scripts/python.exe`:

1. **Recurrence API integration suite**:
   - Command: `./.venv/Scripts/python.exe -m pytest -q tests/integration/test_recurrence_api.py`
   - Outcome: **9 passed**, 10 warnings in 7.75s (0 skipped).
2. **Persistence/rollback suite**:
   - Command: `./.venv/Scripts/python.exe -m pytest -q tests/integration/test_persistence.py`
   - Outcome: **35 passed** in 8.16s (0 skipped).
3. **Recovery verification suite**:
   - Command: `./.venv/Scripts/python.exe -m pytest -q tests/integration/test_recovery_verification_api.py`
   - Outcome: **23 passed**, 14 warnings in 10.00s (0 skipped).
4. **Cause confirmation suite**:
   - Command: `./.venv/Scripts/python.exe -m pytest -q tests/integration/test_cause_confirmation_api.py`
   - Outcome: **17 passed**, 11 warnings in 4.24s (0 skipped).
5. **Check-result and semantic suites**:
   - Command: `./.venv/Scripts/python.exe -m pytest -q tests/integration/test_check_result_api.py tests/integration/test_check_result_diagnosis_revision.py tests/unit/test_check_result_handler.py tests/unit/test_semantic_verification.py`
   - Outcome: **78 passed**, 11 warnings in 5.11s (0 skipped).
6. **Question-answer suites**:
   - Command: `./.venv/Scripts/python.exe -m pytest -q tests/integration/test_question_answer_api.py tests/integration/test_question_answer_diagnosis_revision.py tests/unit/test_question_answer_handler.py tests/unit/test_question_engine.py`
   - Outcome: **34 passed**, 13 warnings in 3.74s (0 skipped).
7. **Durable case, diagnosis, and health suites**:
   - Command: `./.venv/Scripts/python.exe -m pytest -q tests/integration/test_case_api.py tests/integration/test_diagnosis_api.py tests/integration/test_health_api.py`
   - Outcome: **28 passed**, 8 warnings in 2.26s (0 skipped).
8. **Persistence safety suite**:
   - Command: `./.venv/Scripts/python.exe -m pytest -q tests/unit/test_persistence_safety.py`
   - Outcome: **17 passed** in 0.24s (0 skipped).
9. **Full backend test suite**:
   - Command: `./.venv/Scripts/python.exe -m pytest -q`
   - Outcome: **266 passed**, 27 warnings in 35.35s (**0 skipped**).
10. **OpenAPI inspection**:
    - Verified route registration for `POST /api/v1/cases/{case_id}/recurrences` with request body `SubmitRecurrenceRequest` and status codes `200`, `404`, `409`, `422`, `500`.
11. **Task validation**:
    - `python .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-021-recurrence-api.md` passed with `VALID`.
12. **Git diff cleanliness**:
    - `git diff --check` passed cleanly with 0 errors.

### Limitations and follow-up

- Recurrence reporting transitions the case issue condition to `RECURRED`. It does not automatically initiate a new recovery cycle, assign recovery actions, or unconfirm historical causes.
- Case report generation, multimodal computer vision analysis, and LLM integrations remain deferred to future authorized milestones.
