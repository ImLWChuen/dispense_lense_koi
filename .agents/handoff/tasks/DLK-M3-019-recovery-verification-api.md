---
task_id: DLK-M3-019
title: Add durable recovery action and post-correction verification workflow
status: implemented
created_by: planner
assigned_to: implementer
depends_on: DLK-M3-018
feature_branch: backend-database
base_branch: main
---

# DLK-M3-019: Durable recovery action and post-correction verification workflow

## Objective

Expose the next independent issue-lifecycle workflow after explicit cause confirmation.

A technician must be able to:

1. record that a corrective/recovery action has been applied, moving the issue into `RECOVERY_PENDING_VERIFICATION`; and
2. independently record post-correction verification as passed or failed, moving the issue to `RESOLVED` or back to `UNRESOLVED` through the existing state machine.

This task must preserve the product rule that cause confirmation and issue resolution are independent.

A case may therefore validly end in either of these states:

- cause confirmed + issue unresolved;
- cause unconfirmed + issue resolved.

Do not implement recurrence reporting in this task.

## Current evidence

DLK-M3-018 is accepted at reviewed commit:

`0227574b358972bc439416184093ca1b8407125d`

The accepted cause-confirmation workflow now has:

- explicit human confirmation;
- sanitized internal failure handling;
- request/storage boundary alignment;
- immutable revision append;
- stale-revision protection;
- issue condition remaining independent from cause confirmation.

The existing diagnostic domain already defines the issue lifecycle states:

- `UNRESOLVED`
- `RECOVERY_PENDING_VERIFICATION`
- `RESOLVED`
- `RECURRED`

and the existing `StateManager.transition_issue_condition(...)` is the semantic authority for legal transitions.

The current domain contract already requires explicit verification before transition to `RESOLVED`.

## Requirements

Implement one coherent recovery-verification workflow with two explicit durable operations.

### Operation A - record recovery action

Expose:

`POST /api/v1/cases/{case_id}/recovery-actions`

A successful request records that a corrective action has been applied and transitions the issue through the existing state manager to:

`RECOVERY_PENDING_VERIFICATION`

This operation must **not** mark the issue resolved.

### Operation B - verify recovery result

Expose:

`POST /api/v1/cases/{case_id}/recovery-verifications`

A successful verification request is valid only from the state allowed by the existing state machine.

Use the existing transition semantics:

- verification passed -> `RESOLVED`
- verification failed -> `UNRESOLVED`

Do not bypass `StateManager.transition_issue_condition(...)`.

### Independence from root-cause confirmation

Neither recovery action nor verification may require a confirmed cause unless the existing domain state manager already requires it.

Do not introduce such a requirement in the HTTP, repository, or ORM layer.

Verification success may therefore resolve an issue whose root cause remains unconfirmed.

Likewise, a confirmed cause must remain confirmed if recovery verification later fails.

### No recurrence workflow yet

Do not expose transition to `RECURRED` in DLK-M3-019.

Do not add a generic endpoint that accepts arbitrary target issue conditions.

## Interfaces and data contracts

### Recovery-action request

Define an explicit request model containing at minimum:

- `expected_revision`
- `recovery_details`

Optionally allow:

- `performed_by`

If `performed_by` is exposed, constrain it to a storage-compatible maximum of 64 characters from the beginning.

`recovery_details` must describe the applied corrective action and be stored faithfully. Prefer `TEXT` storage for unrestricted details rather than introducing an undocumented VARCHAR limit.

### Recovery-verification request

Define an explicit request model containing at minimum:

- `expected_revision`
- `verification_passed`
- `verification_details`

Optionally allow:

- `verified_by`

If `verified_by` is exposed, constrain it to a storage-compatible maximum of 64 characters.

`verification_passed` is the only client input that selects between the existing allowed verification outcomes:

- `True` -> target `RESOLVED`
- `False` -> target `UNRESOLVED`

The client must not submit an arbitrary target issue condition.

### Status codes

At minimum:

- `200 OK` - transition accepted and committed
- `404 Not Found` - case does not exist
- `409 Conflict` - stale `expected_revision`
- `422 Unprocessable Entity` - illegal lifecycle transition or malformed request
- `500 Internal Server Error` - unexpected internal failure

Known illegal state transitions may return a safe 422 response.

Unexpected internal/domain failures must remain sanitized and must not reflect raw exception details.

### Response

Prefer reuse/extension of the existing durable current-case response contract.

At minimum return:

- `case_id`
- persisted recovery/verification event
- current analysis revision
- current `issue_condition`
- persisted current diagnosis snapshot
- confirmed-cause state already present in the diagnosis

The response must represent committed state.

### Durable lifecycle history

Persist append-only issue-transition audit history.

Use the smallest explicit persistence model that can faithfully record the two transitions in this task.

At minimum each transition event must preserve:

- case ID
- event type
- prior issue condition
- resulting issue condition
- revision number
- actor, if exposed by the request
- details
- verification result where applicable
- creation timestamp

A single append-only issue-transition entity is acceptable.

Do not expose generic CRUD for this history.

### Database migration

One forward Alembic migration is authorized for the minimal lifecycle-event storage.

Do not rewrite existing migration history.

Do not add a migration solely to modify existing diagnosis/case tables unless the current accepted schema cannot support the workflow; return to the planner first if that occurs.

### Revision contract

Each successful lifecycle operation appends exactly one immutable analysis revision.

Global revision ordering must remain shared across all workflow event types.

For example:

- R1 initial diagnosis
- R2 question answer
- R3 troubleshooting check
- R4 cause confirmation
- R5 recovery action
- R6 recovery verification

No workflow owns a separate revision counter.

### Optimistic concurrency

Both endpoints require `expected_revision`.

At the atomic update boundary:

- matching revision -> operation may proceed;
- stale revision -> `409`, no event, no revision, no durable mutation.

Replay using an already-consumed expected revision must return `409`.

### Atomicity

For each successful operation, lifecycle event + case issue condition + Revision N+1 must form one transaction.

If persistence fails:

- no lifecycle event may survive;
- current issue condition must remain unchanged;
- no new revision may survive;
- prior question/check/confirmation histories must remain unchanged.

## Allowed paths

- `backend/app/api/cases.py` or the existing durable case workflow route module
- `backend/app/schemas/case.py`
- `backend/app/models/case.py`
- `backend/app/models/__init__.py` if required
- `backend/app/db/repository.py`
- `backend/alembic/versions/` for one forward lifecycle-history migration
- `backend/tests/integration/test_recovery_verification_api.py`
- `backend/tests/integration/test_persistence.py` only for bounded lifecycle persistence/rollback coverage
- existing issue-state tests only for regression assertions without changing domain semantics
- `docs/api/api-spec.md`
- `docs/database/erd.md`
- `backend/README.md` only if a small local workflow update is useful
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/NEXT-STEPS.md`
- `.agents/handoff/reviews/DLK-M3-018-review.md` (include unchanged)
- `.agents/handoff/tasks/DLK-M3-019-recovery-verification-api.md`

Return to the planner before editing outside this scope.

## Prohibited scope

Do not change:

- `StateManager.transition_issue_condition(...)` semantics
- `IssueCondition` enum values
- cause-confirmation semantics
- question-answer semantics
- troubleshooting-check semantics
- evidence rules or scoring
- existing public answer/check/confirmation contracts
- PostgreSQL test-destination safety

Do not implement:

- `RECURRED` reporting/transition API
- arbitrary issue-state transition endpoint
- recovery deletion/update
- confirmation revocation
- reports/PDF
- image/CV
- LLM integration
- historical retrieval
- authentication/authorization
- frontend integration
- generic CRUD
- background workers/WebSockets
- unrelated dependencies

## Implementation guidance

1. Run full implementation-handoff preflight.
2. Confirm DLK-M3-018 is accepted and DLK-M3-019 is the only `ready` task.
3. Read the current issue-state enum and `StateManager.transition_issue_condition(...)`.
4. Reuse the accepted case lock, reconstruction, transaction, and global revision mechanisms.
5. Define the two request/response contracts before route implementation.
6. Add minimal append-only lifecycle persistence and a forward migration.
7. Implement recovery-action recording through the existing state manager.
8. Implement recovery verification through the existing state manager.
9. Add real PostgreSQL integration tests covering independence, stale writes, legal/illegal transitions, rollback, and mixed revision sequencing.
10. Update API/database documentation.
11. Run focused and complete verification.
12. Complete the implementation report and create one atomic local commit.

## Acceptance criteria

### Recovery action

- [x] `POST /api/v1/cases/{case_id}/recovery-actions` returns `200` for a legal transition.
- [x] `UNRESOLVED` transitions to `RECOVERY_PENDING_VERIFICATION` through the existing state manager.
- [x] The operation does not transition directly to `RESOLVED`.
- [x] One lifecycle event is persisted.
- [x] Exactly one new immutable analysis revision is appended.
- [x] Prior question/check/confirmation history remains unchanged.

### Recovery verification - pass

- [x] Verification from `RECOVERY_PENDING_VERIFICATION` with `verification_passed=true` returns `200`.
- [x] Issue becomes `RESOLVED`.
- [x] Verification evidence/details are persisted faithfully.
- [x] Exactly one lifecycle event and one new revision are appended.
- [x] Cause conclusions are not fabricated or changed merely because verification passed.

### Recovery verification - fail

- [x] Verification from `RECOVERY_PENDING_VERIFICATION` with `verification_passed=false` returns `200`.
- [x] Issue returns to `UNRESOLVED`.
- [x] A previously confirmed cause remains confirmed.
- [x] Verification failure does not erase prior investigation history.
- [x] Exactly one lifecycle event and one new revision are appended.

### Independence

- [x] Recovery may be started without requiring a confirmed root cause.
- [x] A case with no confirmed cause may become `RESOLVED` after explicit successful verification.
- [x] Cause confirmation alone still does not resolve the issue.
- [x] Successful recovery verification does not automatically confirm a cause.

### State-machine enforcement

- [x] Direct verification from `UNRESOLVED` to resolved is rejected as `422`.
- [x] Illegal lifecycle transitions are rejected through the existing state-machine rules.
- [x] No rejected transition appends an event or revision.
- [x] DLK-M3-019 exposes no transition to `RECURRED`.

### Concurrency/replay

- [x] Correct `expected_revision` succeeds.
- [x] Stale `expected_revision` returns `409`.
- [x] Replaying a successful request with the consumed revision returns `409`.
- [x] Stale/replayed requests create no lifecycle event or revision.

### Atomic rollback

- [x] At least one recovery-action rollback test reaches real pending/flushed lifecycle-event + revision writes before injected failure.
- [x] At least one verification rollback test reaches real pending/flushed lifecycle-event + revision writes before injected failure.
- [x] Production transaction management performs rollback naturally.
- [x] Fresh independent session finds no attempted lifecycle event or revision.
- [x] Case issue condition remains at its pre-request value.
- [x] Prior answer/check/confirmation histories and snapshots remain unchanged.
- [x] Unrelated control case remains unchanged.
- [x] Failure response is sanitized.

### Mixed revision history

- [x] A sequence containing question answer, check result, cause confirmation, recovery action, and recovery verification uses one monotonic global revision sequence.
- [x] No event type resets or owns its own revision numbering.
- [x] Earlier revisions remain immutable.

### Regression

- [x] Cause-confirmation API remains unchanged.
- [x] Check-result workflow remains unchanged.
- [x] Question-answer workflow remains unchanged.
- [x] Durable case and stateless diagnosis APIs remain unchanged.
- [x] Existing semantic, persistence, and safety suites pass.
- [x] No recurrence API is introduced.
- [x] Only authorized files change.
- [x] No remote Git operation occurs.

## Verification

Use the accepted verified local PostgreSQL test database.

From `backend/`, run at minimum:

1. apply current migration head:
   `.\.venv\Scripts\python.exe -m alembic upgrade head`

2. new recovery workflow:
   `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_recovery_verification_api.py`

3. relevant persistence/rollback coverage:
   `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_persistence.py`

4. cause-confirmation API suite;

5. check-result API + semantic suites;

6. question-answer API/revision suites;

7. durable case + diagnosis + health suites;

8. persistence-safety suite;

9. complete backend suite:
   `.\.venv\Scripts\python.exe -m pytest -q`

10. inspect OpenAPI and verify both new routes plus all existing routes/contracts.

From repository root:

11. validate the task:
    `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-019-recovery-verification-api.md`

12. `git diff --check`

13. inspect `git status`, staged names, and the full staged diff before commit.

If real PostgreSQL verification cannot run, mark the task `blocked`; do not substitute SQLite for required transaction proof.

## Planner decision boundaries

Return to the planner before:

- changing issue-state semantics;
- changing `StateManager.transition_issue_condition(...)`;
- requiring cause confirmation before recovery;
- allowing resolution without explicit verification;
- implementing recurrence;
- creating an arbitrary target-state endpoint;
- changing existing public workflow contracts;
- adding dependencies outside the existing persistence stack;
- changing case/revision identity semantics.

## Git instructions

After all acceptance criteria pass:

- complete the DLK-M3-019 implementation report;
- mark DLK-M3-019 and `QUEUE.md` as `implemented`;
- inspect staged names and the full staged diff;
- create exactly one atomic local commit.

Proposed commit message:

`feat(api): add recovery verification workflow`

Do not push, merge, rebase, create/update a pull request, or modify `main`.

## Implementation report

### Summary

Implemented the durable recovery action and post-correction verification workflow for precision dispensing cases, establishing the complete issue lifecycle from `UNRESOLVED` -> `RECOVERY_PENDING_VERIFICATION` -> `RESOLVED` / `UNRESOLVED`.
- Added `POST /api/v1/cases/{case_id}/recovery-actions` to record corrective action and transition the case issue condition to `RECOVERY_PENDING_VERIFICATION` via domain `StateManager`.
- Added `POST /api/v1/cases/{case_id}/recovery-verifications` to record explicit verification outcome (`verification_passed = True` -> `RESOLVED`, `verification_passed = False` -> `UNRESOLVED`) via domain `StateManager`.
- Maintained strict independence between root-cause confirmation and issue condition: an issue can be resolved with or without a confirmed root cause, and a confirmed root cause remains confirmed even when verification fails.
- Enforced optimistic concurrency control via `expected_revision` on both endpoints (returning 409 on stale or replayed writes).
- Persisted minimal append-only audit history in `case_lifecycle_events` using forward Alembic migration `0006_lifecycle_event_history.py`.
- Enforced atomic transactions on failure with zero surviving event rows or revision rows.
- Verified monotonic global revision ordering across all five event types (initial diagnosis, question answer, troubleshooting check, cause confirmation, recovery action, recovery verification).

### Files changed

- `backend/alembic/versions/0006_lifecycle_event_history.py`: Forward migration adding `case_lifecycle_events` table with constraints and indices.
- `backend/app/models/case.py`: Added `CaseLifecycleEventModel` ORM mapping and `lifecycle_events` relationship on `CaseModel`.
- `backend/app/models/__init__.py`: Exported `CaseLifecycleEventModel`.
- `backend/app/schemas/case.py`: Added Pydantic schemas: `LifecycleEventRecord`, `SubmitRecoveryActionRequest` (performed_by max_length=64), `SubmitRecoveryVerificationRequest` (verified_by max_length=64), `CaseRecoveryActionResponse`, and `CaseRecoveryVerificationResponse`.
- `backend/app/db/repository.py`: Added `get_case_lifecycle_events`, `append_lifecycle_event_revision`, `append_recovery_action_revision`, and `append_recovery_verification_revision`.
- `backend/app/api/cases.py`: Implemented `POST /api/v1/cases/{case_id}/recovery-actions` and `POST /api/v1/cases/{case_id}/recovery-verifications` with optimistic locking (409), legal transitions (422), independent cause handling, and sanitized 500 error responses.
- `backend/tests/integration/test_recovery_verification_api.py`: Comprehensive test suite (17 tests) covering OpenAPI schema, legal/illegal transitions, independence, stale revisions, replay protection, actor 64-char boundary, validation errors, and `before_commit` rollback for both operations.
- `backend/tests/integration/test_persistence.py`: Added repository-level flush-boundary rollback tests for recovery action and recovery verification, plus mixed 5-event-type monotonic revision ordering test (all 33 tests pass).
- `docs/api/api-spec.md`: Added Section 7 detailing recovery action and verification API endpoints, request/response schemas, status codes, and error examples.
- `docs/database/erd.md`: Added `case_lifecycle_events` table specification, Mermaid entity, and architectural guarantee #7.
- `.agents/handoff/QUEUE.md`: Marked DLK-M3-019 as implemented.
- `.agents/handoff/tasks/DLK-M3-019-recovery-verification-api.md`: Updated checklist and completed implementation report.

### Recovery-action API contract

- Path: `POST /api/v1/cases/{case_id}/recovery-actions`
- Request Schema:
  - `expected_revision`: int (>= 1, required)
  - `recovery_details`: str (non-empty, required)
  - `performed_by`: str (optional, max 64 chars, default "technician")
- Response Schema: `CaseRecoveryActionResponse` (contains `case_id`, `issue_condition = RECOVERY_PENDING_VERIFICATION`, `current_revision`, `submitted_recovery_action`, `lifecycle_events`, and updated diagnosis).
- Behavior: Transitions issue condition to `RECOVERY_PENDING_VERIFICATION` via `StateManager`. Does not mark the issue resolved.

### Recovery-verification API contract

- Path: `POST /api/v1/cases/{case_id}/recovery-verifications`
- Request Schema:
  - `expected_revision`: int (>= 1, required)
  - `verification_passed`: bool (required)
  - `verification_details`: str (non-empty, required)
  - `verified_by`: str (optional, max 64 chars, default "technician")
- Response Schema: `CaseRecoveryVerificationResponse` (contains `case_id`, updated `issue_condition`, `current_revision`, `submitted_recovery_verification`, `lifecycle_events`, and updated diagnosis).
- Behavior:
  - `verification_passed = True` -> `RESOLVED`
  - `verification_passed = False` -> `UNRESOLVED`
  - Requires case to currently be in `RECOVERY_PENDING_VERIFICATION`; other source states return 422.

### Lifecycle persistence/revision decisions

- Table `case_lifecycle_events`:
  - `id`: serial primary key
  - `case_id`: UUID foreign key with CASCADE delete
  - `event_type`: VARCHAR(64) (`RECOVERY_ACTION` or `RECOVERY_VERIFICATION`)
  - `prior_issue_condition`: VARCHAR(64)
  - `resulting_issue_condition`: VARCHAR(64)
  - `resulting_revision_number`: INTEGER (> 1, unique with case_id)
  - `actor`: VARCHAR(64)
  - `details`: TEXT
  - `verification_passed`: BOOLEAN (nullable)
  - `created_at`: TIMESTAMPTZ
- Global revision numbering is shared across all workflow event types; each accepted action or verification produces exactly one immutable `AnalysisRevision` record and one `CaseLifecycleEvent` record.

### Cause/issue independence proof

- `test_recovery_without_confirmed_cause_and_verification_resolves_issue`: Proves a case with 0 confirmed causes can successfully transition through `RECOVERY_PENDING_VERIFICATION` to `RESOLVED`.
- `test_recovery_verification_failure_reverts_to_unresolved_and_preserves_confirmed_cause`: Proves an issue with a previously confirmed cause ("pressure_instability") transitions back to `UNRESOLVED` when verification fails, while the cause remains `CONFIRMED` in the latest diagnosis revision.
- `test_direct_verification_from_unresolved_is_rejected_422`: Proves state manager forbids bypassing verification directly from `UNRESOLVED`.

### Rollback verification

- `test_recovery_action_before_commit_rollback_leaves_database_clean`: Injected failure at session `before_commit` during API recovery-action submission leaves zero lifecycle events, preserves baseline `issue_condition`, and returns sanitized 500.
- `test_recovery_verification_before_commit_rollback_leaves_database_clean`: Injected failure at session `before_commit` during API recovery-verification submission leaves zero verification events, preserves baseline `issue_condition`, and returns sanitized 500.
- `test_append_recovery_action_revision_rollback_on_failure`: Repository-level rollback test in `test_persistence.py` confirms target and control case states remain identical to baseline in fresh session.
- `test_append_recovery_verification_revision_rollback_on_failure`: Repository-level rollback test in `test_persistence.py` confirms target and control case states remain identical to baseline in fresh session.

### Verification results

All verification steps executed against real PostgreSQL test container:
1. `alembic upgrade head`: Clean, at head.
2. `pytest -q tests/integration/test_recovery_verification_api.py`: 17 passed in 6.39s.
3. `pytest -q tests/integration/test_persistence.py`: 33 passed in 6.82s.
4. `pytest -q tests/integration/test_cause_confirmation_api.py`: 17 passed in 4.32s.
5. Check result test suite: 42 passed in 5.00s.
6. Question answer test suite: 34 passed in 3.59s.
7. Durable case, diagnosis, and health suites: 28 passed in 2.14s.
8. Persistence safety suite: 17 passed in 0.23s.
9. Full backend pytest suite: 249 passed, 0 failed in 23.06s.
10. OpenAPI routes inspected: `/api/v1/cases/{case_id}/recovery-actions` and `/api/v1/cases/{case_id}/recovery-verifications` verified.
11. `validate_task.py`: Passed (VALID).
12. `git diff --check`: Clean (0 errors).

### Limitations and follow-up

- Recurrence workflow (`RECURRED`) is intentionally deferred to future tasks.
- Frontend integration for recovery actions and verification to follow.

### Proposed commit message

`feat(api): add recovery verification workflow`
