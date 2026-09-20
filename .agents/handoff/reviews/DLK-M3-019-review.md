---
task_id: DLK-M3-019
reviewed_commit: d881b44b59a80bbefd173d180541ae884fbf87ed
decision: changes_requested
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-019

## Decision

Changes requested for the bounded findings below. Preserve existing domain semantics and the cause/issue independence already implemented.

## Acceptance evidence

- Reviewed committed route, repository, schema, migration, rollback tests, and implementation report. Working tree was clean on backend-database at review start.
- Both operations use the state manager and append lifecycle history plus a shared analysis revision in the existing transaction. Repository append locks the case and checks expected_revision. Actor fields have 64-character request limits and details use TEXT storage.
- Tests cover recovery without cause confirmation, successful verification, failed verification preserving a confirmed cause, mixed revision ordering, and API/repository rollback.
- Gemini reports 249 backend tests passing, 17 recovery API tests, 33 persistence tests, and migration head applied against PostgreSQL. These are implementer-reported results; reviewer did not rerun database tests or migrations.
- Reviewer task validator returned VALID and committed whitespace inspection passed.

## Findings

### R1 - P2: Require pending recovery before accepting verification

backend/app/api/cases.py:1391-1401 checks only whether the target is in the general state-manager transition map. That map allows UNRESOLVED -> UNRESOLVED and RESOLVED -> RESOLVED. Consequently a fresh unresolved case with verification_passed=false is accepted without a recovery action, and a resolved case with a fresh expected_revision and verification_passed=true appends another verification despite having no pending recovery. This contradicts the documented requirement that verification requires RECOVERY_PENDING_VERIFICATION. The stale-replay check cannot reject requests carrying the current revision.

Add the operation-specific pending-state precondition, returning safe 422 before mutation, and still invoke the existing state manager for the actual legal transition. Do not change its general transition map. Test both outcomes from UNRESOLVED and RESOLVED with current revision numbers, and verify no lifecycle event, revision, or case/history mutation. Keep pending-state pass/fail behavior working.

### R2 - P2: Sanitize unexpected state-manager ValueErrors

backend/app/api/cases.py:1094-1098 and 1410-1414 catch every ValueError from transition_issue_condition and interpolate its message into HTTP 422. Both paths already prevalidate the target transition, so an unexpected internal ValueError from a legal transition is incorrectly exposed to the client. A synthetic private-path exception from that method would leak verbatim. The packet explicitly requires unexpected internal/domain failures to remain sanitized.

Keep known illegal transitions as controlled 422 responses, but let unexpected state-manager failures reach the logged sanitized 500 handler. Add bounded tests for both operations injecting a ValueError with a sensitive marker during an otherwise legal transition; assert 500, no marker/raw details, and no durable mutation. Preserve the existing state-manager semantics.

### R3 - P2: Verify preservation of confirmation and lifecycle audit history on rollback

backend/tests/integration/test_recovery_verification_api.py:582-776 compares capture_complete_case_state before and after failed action/verification submissions. That helper contains no confirmation or lifecycle records (backend/tests/case_snapshot_helper.py return mapping). The API rollback baselines contain only prior answers/checks, so the comparisons cannot prove the task's required preservation of confirmation history. The verification rollback checks only absence of the attempted event, leaving its already persisted recovery-action record outside the comparison. Repository rollback tests use the same incomplete helper.

Extend the rollback evidence for both operations with an actual prior confirmation and detached snapshots of confirmation and lifecycle history, captured in independent sessions. Compare complete stored values after failure for target and control, including the prior recovery event for verification. Use a bounded test-local helper if changing the shared helper requires additional scope. Preserve the existing pending-write fault injection and outside-handler assertions. This is a verification correction, not a request to redesign persistence.

## Follow-up

Carry R1-R3 into the next bounded correction packet before dependent feature work. No new task generated and no production fixes applied in this review. Review/queue changes remain local and uncommitted. No commit, push, or merge performed.
