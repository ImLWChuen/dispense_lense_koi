---
task_id: DLK-M3-020
title: Close recovery verification preconditions, error sanitization, and rollback proof
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-019]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-020: Recovery-verification workflow closeout

## Objective

Close the three bounded findings blocking acceptance of DLK-M3-019 without redesigning the issue lifecycle, persistence model, or domain state machine.

This task must:

1. require `RECOVERY_PENDING_VERIFICATION` before any recovery-verification submission is accepted;
2. preserve controlled `422` responses for known illegal lifecycle requests while routing unexpected state-manager `ValueError`s to a sanitized `500`; and
3. complete rollback proof by preserving and comparing prior cause-confirmation and lifecycle audit history in addition to existing case/answer/check/revision state.

DLK-M3-019 remains unaccepted until this correction is implemented and reviewed.

## Current evidence

DLK-M3-019 was reviewed at commit:

`d881b44b59a80bbefd173d180541ae884fbf87ed`

The review returned `changes_requested`.

### R1 — verification can be submitted without pending recovery

The existing general transition map permits self-transitions such as:

- `UNRESOLVED -> UNRESOLVED`
- `RESOLVED -> RESOLVED`

The recovery-verification endpoint currently relies only on that general map. This incorrectly allows failed verification on a fresh unresolved case and repeated successful verification on an already resolved case when the caller uses the current revision.

### R2 — unexpected state-manager ValueErrors can leak

Both recovery endpoints currently convert any `ValueError` raised by `transition_issue_condition(...)` into HTTP `422` and expose the raw exception text.

Known illegal requests should remain controlled `422`. Unexpected internal failures during an otherwise legal transition must become sanitized `500`.

### R3 — rollback comparisons omit confirmation/lifecycle audit history

Current rollback snapshots do not prove preservation of prior cause-confirmation records or lifecycle events. Verification rollback also does not fully compare the already-persisted recovery-action event that created the pending-verification state.

## Requirements

### R1 — require pending recovery before verification

`POST /api/v1/cases/{case_id}/recovery-verifications` must accept a verification request only when the current persisted issue condition is:

`RECOVERY_PENDING_VERIFICATION`

This applies to both:

- `verification_passed=true`
- `verification_passed=false`

If current issue condition is anything else, return `422 Unprocessable Entity` before lifecycle mutation.

This is an operation-specific API precondition. Do not modify the general `StateManager` transition map.

After the precondition passes, continue to invoke the existing `StateManager.transition_issue_condition(...)` for the actual domain transition.

### Required invalid-state regression matrix

Using current, non-stale revision numbers, test:

1. `UNRESOLVED` + pass -> `422`
2. `UNRESOLVED` + fail -> `422`
3. `RESOLVED` + pass -> `422`
4. `RESOLVED` + fail -> `422`

Each must prove:

- no lifecycle event appended;
- no revision appended;
- current revision unchanged;
- issue condition unchanged;
- prior answer history unchanged;
- prior check history unchanged;
- prior confirmation history unchanged when present;
- prior lifecycle history unchanged.

Tests must use the current revision so rejection cannot be attributed to stale concurrency protection.

Retain:

- `RECOVERY_PENDING_VERIFICATION` + pass -> `RESOLVED`
- `RECOVERY_PENDING_VERIFICATION` + fail -> `UNRESOLVED`

### R2 — sanitize unexpected state-manager failures

### Known client errors

Known illegal lifecycle requests must continue to return controlled `422` responses through explicit prevalidation.

Do not expose raw exception messages to achieve that behavior.

### Unexpected failures

For both:

- `POST /api/v1/cases/{case_id}/recovery-actions`
- `POST /api/v1/cases/{case_id}/recovery-verifications`

an unexpected `ValueError` raised by `StateManager.transition_issue_condition(...)` during an otherwise legal transition must:

- return sanitized `500 Internal Server Error`;
- not expose `str(e)`;
- not expose synthetic sensitive markers/private paths;
- append no lifecycle event;
- append no revision;
- leave issue condition unchanged;
- leave prior histories unchanged.

Do not convert the unexpected failure to `422` merely because the Python exception class is `ValueError`.

### Required R2 tests

Add one injected internal-failure regression per endpoint.

For recovery action:

- establish a legal source state;
- use current revision;
- patch/inject `transition_issue_condition(...)` to raise a `ValueError` containing a synthetic sensitive marker/private path;
- expect sanitized `500`;
- prove marker/raw text absent;
- prove no durable mutation.

For recovery verification:

- establish `RECOVERY_PENDING_VERIFICATION`;
- use current revision;
- inject the same class of internal failure;
- expect sanitized `500`;
- prove no durable mutation.

Retain known-illegal-transition `422` coverage.

### R3 — complete rollback preservation proof

For both rollback targets, establish meaningful prior durable history before the failing operation.

At minimum include:

- prior question-answer history;
- prior troubleshooting-check history;
- at least one prior cause-confirmation record.

For the recovery-verification rollback case, also include:

- the already-persisted recovery-action lifecycle event that placed the case into `RECOVERY_PENDING_VERIFICATION`.

Rollback assertions must compare detached stored values for:

- case/core state;
- observations;
- analysis revisions and full result snapshots;
- question-answer history;
- check-result history;
- cause-confirmation history;
- lifecycle-event history.

For verification rollback, prove the pre-existing recovery-action event remains present and byte/value-equivalent after the failure. Do not merely assert the attempted verification event is absent.

Capture baseline state in an independent session. After failure, use a fresh independent session to compare complete stored values.

Preserve the existing post-write rollback strengths:

- real production append path;
- actual pending/flushed lifecycle + revision writes before injected failure;
- failure before commit;
- natural production rollback;
- no manual rollback as the mechanism under test;
- existing fault-reached/outside-handler assertions;
- unrelated control case unchanged;
- sanitized HTTP failure.

If safely possible, extend the shared complete-case snapshot helper with confirmation and lifecycle history. Otherwise use a bounded test-local helper. Do not change production persistence simply to make snapshots easier.

## Interfaces and data contracts

No API redesign is authorized.

Preserve:

- both recovery endpoints;
- request/response schemas;
- actor length limits;
- TEXT details storage;
- stale revision `409`;
- missing case `404`;
- successful lifecycle semantics;
- global revision sequence;
- lifecycle audit persistence;
- cause/issue independence.

The only intended behavior changes are:

1. recovery verification requires `RECOVERY_PENDING_VERIFICATION`;
2. unexpected state-manager failures become sanitized `500`.

## Domain ownership boundary

Do not change:

- `IssueCondition` values;
- `StateManager.transition_issue_condition(...)` transition map;
- cause-confirmation semantics;
- question-answer semantics;
- troubleshooting-check semantics;
- evidence/scoring;
- recovery-action meaning;
- successful verification meaning.

If a fix requires changing those semantics, stop and return the blocker to the planner.

## Implementation guidance

Apply R1, R2, and R3 above within the allowed paths, preserve the contracts and domain ownership boundaries, and run the specified verification before completing the implementation report.

## Allowed paths

- `backend/app/api/cases.py`
- `backend/tests/integration/test_recovery_verification_api.py`
- `backend/tests/integration/test_persistence.py`
- `backend/tests/case_snapshot_helper.py` only if bounded extension is appropriate
- existing recovery test helpers/fixtures only when required
- `docs/api/api-spec.md`
- `backend/README.md` only if precondition/error behavior is documented there
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/NEXT-STEPS.md` only for closeout progression
- `.agents/handoff/reviews/DLK-M3-019-review.md` unchanged
- `.agents/handoff/tasks/DLK-M3-019-recovery-verification-api.md` only for narrow report correction if needed
- `.agents/handoff/tasks/DLK-M3-020-recovery-verification-closeout.md`

Return to the planner before editing outside this scope.

## Prohibited scope

Do not change:

- ORM models;
- Alembic migrations;
- database schema;
- repository transaction design unless a new failing test proves a production defect and the planner explicitly expands scope;
- state-manager implementation;
- enum values;
- dependencies;
- PostgreSQL destination-safety policy.

Do not add:

- recurrence API;
- generic issue-state transition API;
- recovery edit/delete;
- report generation;
- auth;
- frontend code;
- LLM/CV;
- generic CRUD.

## Acceptance criteria

### R1

- [x] Verification from `UNRESOLVED` + pass returns `422`.
- [x] Verification from `UNRESOLVED` + fail returns `422`.
- [x] Verification from `RESOLVED` + pass returns `422`.
- [x] Verification from `RESOLVED` + fail returns `422`.
- [x] All four use current revision.
- [x] No lifecycle event/revision is appended.
- [x] Issue condition and complete prior history are unchanged.
- [x] Pending-state pass still succeeds.
- [x] Pending-state fail still succeeds.
- [x] General state-manager map remains unchanged.

### R2

- [x] Legal recovery action + injected internal `ValueError` returns sanitized `500`.
- [x] Legal recovery verification + injected internal `ValueError` returns sanitized `500`.
- [x] No sensitive marker/raw exception text is returned.
- [x] Neither failure appends lifecycle history or revision.
- [x] Neither changes issue condition.
- [x] Complete prior durable state remains unchanged.
- [x] Known illegal requests remain controlled `422`.

### R3

- [x] Recovery-action rollback baseline includes prior confirmation.
- [x] Recovery-verification rollback baseline includes prior confirmation.
- [x] Verification rollback baseline includes the prior recovery-action event.
- [x] Snapshot comparison includes confirmation history.
- [x] Snapshot comparison includes lifecycle history.
- [x] Baseline/post-failure capture uses independent sessions.
- [x] Full target and control state remain unchanged after rollback.
- [x] Existing pending-write/fault-reached assertions remain.
- [x] Attempted lifecycle/revision writes are absent after rollback.

### Regression

- [x] Recovery action happy path unchanged.
- [x] Pending-state verification pass/fail unchanged.
- [x] Cause confirmation remains independent from issue resolution.
- [x] Check-result workflow passes.
- [x] Question-answer workflow passes.
- [x] Cause-confirmation workflow passes.
- [x] Persistence/safety suites pass.
- [x] Complete backend suite passes.
- [x] No migration/schema change.
- [x] Only authorized files change.
- [x] No remote Git operation occurs.

## Documentation

Update `docs/api/api-spec.md` to state:

- recovery verification is accepted only when current issue condition is `RECOVERY_PENDING_VERIFICATION`;
- verification from `UNRESOLVED` or `RESOLVED` returns controlled `422`;
- unexpected internal transition failures return sanitized `500`;
- raw internal exception details are not reflected.

Do not add recurrence semantics.

## Verification

Use the accepted local PostgreSQL test database.

From `backend/`, run at minimum:

1. `\.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_recovery_verification_api.py`
2. `\.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_persistence.py`
3. cause-confirmation API suite
4. check-result API + semantic suites
5. question-answer API/revision suites
6. durable case + diagnosis + health suites
7. persistence-safety suite
8. `\.\.venv\Scripts\python.exe -m pytest -q`

Inspect OpenAPI and verify the existing recovery routes remain stable.

From repository root:

9. `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-020-recovery-verification-closeout.md`
10. `git diff --check`
11. inspect `git status`, staged names, and full staged diff before commit.

If real PostgreSQL verification cannot run, mark the task `blocked`.

## Planner decision boundaries

Return to the planner before:

- modifying the general state-transition map;
- changing successful recovery semantics;
- changing lifecycle schema;
- changing repository transaction design;
- introducing recurrence;
- changing existing success response structures;
- adding dependencies;
- expanding into reports/frontend integration.

## Git instructions

After all acceptance criteria pass:

- complete the DLK-M3-020 implementation report;
- mark DLK-M3-020 and `QUEUE.md` as `implemented`;
- inspect staged names/full diff;
- create one atomic local correction commit.

Proposed commit message:

`fix(api): close out recovery verification workflow`

Do not push, merge, rebase, create/update a pull request, or modify `main`.

## Implementation report

### Summary

Successfully addressed all three review findings (R1, R2, R3) identified during review of DLK-M3-019 without modifying the general `StateManager` transition map, database schema, or persistence architecture.

1. **R1:** Implemented an operation-specific API precondition in `POST /api/v1/cases/{case_id}/recovery-verifications` requiring `current_condition == IssueCondition.RECOVERY_PENDING_VERIFICATION` before any state transition is attempted. Requests from `UNRESOLVED` or `RESOLVED` (for both passed and failed verifications) return controlled HTTP 422 without mutation.
2. **R2:** Removed blanket `try ... except ValueError as e: raise HTTPException(422, ...)` blocks in `submit_recovery_action` and `submit_recovery_verification`. Known illegal requests are pre-validated (returning 422), while unexpected internal `ValueError`s during transitions route to sanitized HTTP 500 without leaking raw exception text, synthetic markers, or private file paths.
3. **R3:** Extended `capture_complete_case_state()` helper to include detached immutable representations of `cause_confirmations` and `lifecycle_events`. Updated recovery action and recovery verification rollback tests across both API integration and repository persistence suites to include meaningful prior history (QA, Check, Cause Confirmation, and prior Recovery Action event for verification). Verified in independent sessions that target and control states match baselines exactly after rollback.

### Files changed

- `backend/app/api/cases.py`: Added `RECOVERY_PENDING_VERIFICATION` precondition in `POST /api/v1/cases/{case_id}/recovery-verifications` returning 422. Removed `except ValueError` blocks in both recovery endpoints so unexpected domain manager errors bubble to sanitized 500 handler.
- `backend/tests/case_snapshot_helper.py`: Extended `capture_complete_case_state` to query and include `cause_confirmations` (ordered by `resulting_revision_number.asc(), cause_id.asc()`) and `lifecycle_events` (ordered by `resulting_revision_number.asc(), event_type.asc()`).
- `backend/tests/integration/test_recovery_verification_api.py`: Added `_advance_case_to_rev4_with_confirmation` helper. Added full 4-case R1 invalid-state regression matrix (`UNRESOLVED` pass/fail, `RESOLVED` pass/fail) using non-stale revision numbers. Added R2 unexpected error sanitization tests with monkeypatched `ValueError` containing synthetic sensitive leaks for both endpoints. Updated R3 rollback tests with Rev 4 confirmation baseline, Rev 5 recovery action event baseline, and complete snapshot equality assertions.
- `backend/tests/integration/test_persistence.py`: Updated `test_append_recovery_action_revision_rollback_on_failure` and `test_append_recovery_verification_revision_rollback_on_failure` with Rev 4 cause confirmation and Rev 5 recovery action baselines, asserting full snapshot equality and lifecycle event persistence.
- `docs/api/api-spec.md`: Documented the `RECOVERY_PENDING_VERIFICATION` precondition, controlled 422 for invalid states, and sanitized 500 error handling in Section 7.
- `.agents/handoff/QUEUE.md`: Marked DLK-M3-020 as `implemented`.
- `.agents/handoff/tasks/DLK-M3-020-recovery-verification-closeout.md`: Updated status to `implemented`, checked all criteria, and completed implementation report.

### R1 pending-recovery precondition

- In `backend/app/api/cases.py` (`POST /api/v1/cases/{case_id}/recovery-verifications`): Checked `if current_condition != IssueCondition.RECOVERY_PENDING_VERIFICATION: raise HTTPException(422, ...)`.
- Added tests in `test_recovery_verification_api.py`:
  - `test_recovery_verification_from_unresolved_pass_rejected_422`
  - `test_recovery_verification_from_unresolved_fail_rejected_422`
  - `test_recovery_verification_from_resolved_pass_rejected_422`
  - `test_recovery_verification_from_resolved_fail_rejected_422`
- Verified all 4 tests use current non-stale revisions, return 422, append 0 revisions/events, and leave entire baseline snapshot completely unchanged.
- Verified legal transitions from `RECOVERY_PENDING_VERIFICATION` (`verification_passed=True` -> `RESOLVED`, `verification_passed=False` -> `UNRESOLVED`) continue to succeed.

### R2 state-manager error sanitization

- Removed `except ValueError` wrapping `StateManager.transition_issue_condition` in both endpoints in `cases.py`.
- Known illegal transitions are caught prior to transition invocation via explicit prevalidation and return 422.
- Unexpected errors bubble up to outer exception handlers returning sanitized 500 (`"An unexpected error occurred while submitting the recovery action."` / `"An unexpected error occurred while submitting the recovery verification."`).
- Added tests in `test_recovery_verification_api.py`:
  - `test_recovery_action_unexpected_state_manager_value_error_returns_sanitized_500`
  - `test_recovery_verification_unexpected_state_manager_value_error_returns_sanitized_500`
- Both tests monkeypatch `transition_issue_condition` to raise `ValueError("SYNTHETIC_SENSITIVE_LEAK: /private/internal/secret_core_path.py line 42")` and assert status 500, absence of leak markers in response text, and complete baseline state preservation.

### R3 rollback-history verification

- Updated `capture_complete_case_state` in `case_snapshot_helper.py` to capture `cause_confirmations` and `lifecycle_events`.
- In `test_recovery_verification_api.py`:
  - Recovery action rollback uses target and control cases advanced to Rev 4 with QA, check result, and confirmed root cause. Attempted revision is 5. After rollback, target matches baseline exactly with 1 QA, 1 check, 1 confirmation, 0 lifecycle events.
  - Recovery verification rollback uses target and control cases advanced to Rev 5 with QA, check, confirmation, and recovery action event. Attempted revision is 6. After rollback, target matches baseline exactly with 1 QA, 1 check, 1 confirmation, and exactly 1 lifecycle event (`RECOVERY_ACTION` at revision 5).
- In `test_persistence.py`:
  - Updated `test_append_recovery_action_revision_rollback_on_failure` and `test_append_recovery_verification_revision_rollback_on_failure` to establish identical baselines and assert exact preservation in fresh independent sessions.

### Verification results

All suites executed against real PostgreSQL container:
- `backend/tests/integration/test_recovery_verification_api.py`: 23 passed in 9.76s
- `backend/tests/integration/test_persistence.py`: 33 passed in 7.04s
- Integration suites (cause confirmation, check results, question answers, case, diagnosis, health, persistence safety): 114 passed in 12.06s
- Complete backend suite: 255 passed in 28.38s (0 failures, 0 errors)
- `validate_task.py`: PASSED (VALID: `.agents\handoff\tasks\DLK-M3-020-recovery-verification-closeout.md`)
- `git diff --check`: PASSED (no whitespace or format errors)

### Limitations and follow-up

- Recurrence transition (`RECURRED`) and reporting endpoints remain out of scope for this task and blocked in `QUEUE.md` until milestone progression.
- Scope was strictly preserved without schema changes, model modifications, or changes to the general `StateManager` transition map.

### Proposed commit message

`fix(api): close out recovery verification workflow`
