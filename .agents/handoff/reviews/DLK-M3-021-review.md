---
task_id: DLK-M3-021
reviewed_commit: ff8a4d9ccaef2f7be2dc539c77cf4c46d963739f
decision: accepted
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-021

## Decision

Accepted for the scoped recurrence workflow. This replaces the earlier blocked working-tree review. The implementation is committed locally and verification is reported. No blocking production correctness finding was identified.

## Acceptance evidence

- Reviewed commit ff8a4d9ccaef2f7be2dc539c77cf4c46d963739f on backend-database. Changes stay within allowed paths; no migration or domain state-manager change.
- The endpoint explicitly requires RESOLVED, checks expected_revision, calls StateManager.transition_issue_condition, and persists through append_recurrence_revision. The existing lifecycle append locks the case and rechecks revision before atomically appending the event and N+1 snapshot. The response is constructed before commit and returned after commit.
- Tests cover source-state rejection, stale/replay conflict, missing cases, validation, confirmed/unconfirmed causes, sanitized internal failures, and the seven-revision workflow.
- API rollback injection occurs at before_commit after pending writes are flushed. Fresh-session target/control snapshots verify rollback of event and revision and preservation of prior answers, checks, confirmation, and lifecycle history. Repository coverage uses the self-managed production rollback path.
- Implementer-reported PostgreSQL results: recurrence 9 passed; persistence 35 passed; recovery verification 23 passed; cause confirmation 17 passed; full backend 266 passed, 0 skipped. Other regression and safety commands/results are recorded in the task.
- Reviewer independently checked committed diff whitespace: passed. Task validator: VALID. Database tests were not rerun by the reviewer under the project role split; runtime results above are implementer-reported.

## Nonblocking documentation correction

Carry these task-report corrections into the next authorized task. The actual API specification and code agree; do not change the working API to match the inaccurate report:

- Actual methods are append_recurrence_revision and append_lifecycle_event_revision, not append_recurrence_event / append_lifecycle_event.
- Actual state-manager call is transition_issue_condition, not record_recurrence.
- Actual response uses current_revision, submitted_recurrence, submitted_event, lifecycle_events, and diagnosis.analysis_revision. The event actor field is actor. The report's lifecycle_event, revision, source_event_type, source_event_id, and event reported_by descriptions are not the implemented response contract.

These are report corrections, not production blockers. Use backend/app/schemas/case.py and docs/api/api-spec.md for integration.

## Follow-up

DLK-M3-021 is accepted. No next task generated. Future implementation requires an authorized task packet. Review and queue edits remain local and uncommitted; no push or merge performed.
