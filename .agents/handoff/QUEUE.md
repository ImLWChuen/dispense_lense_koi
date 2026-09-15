# Implementation Queue

## Current milestone

Recovery-verification workflow closeout

## Review state

- `DLK-M3-019` — Durable recovery action and post-correction verification workflow — **changes_requested**
  - reviewed commit: `d881b44b59a80bbefd173d180541ae884fbf87ed`
  - blockers:
    - require `RECOVERY_PENDING_VERIFICATION` before any verification submission
    - sanitize unexpected state-manager `ValueError`s as HTTP 500
    - prove rollback preserves prior confirmation and lifecycle audit history

## Ready

- `DLK-M3-020` — Recovery-verification workflow closeout — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-020-recovery-verification-closeout.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-019`

## Not released

Blocked until DLK-M3-020 is implemented and accepted:

- resolved-issue recurrence reporting (`RECURRED`)
- report generation
- image/CV integration
- LLM integration
- historical-case retrieval
- frontend recovery/verification integration

Only DLK-M3-020 is authorized for implementation.
