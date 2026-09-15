# Implementation Queue

## Current milestone

Recovery-verification workflow closeout — complete

## Review state

- `DLK-M3-019` — Durable recovery action and post-correction verification workflow — **changes_requested**
  - reviewed commit: `d881b44b59a80bbefd173d180541ae884fbf87ed`
  - historical decision at the earlier commit; all three findings resolved by accepted DLK-M3-020
  - resolved findings:
    - require `RECOVERY_PENDING_VERIFICATION` before any verification submission
    - sanitize unexpected state-manager `ValueError`s as HTTP 500
    - prove rollback preserves prior confirmation and lifecycle audit history

## Latest accepted task

- `DLK-M3-020` — Recovery-verification workflow closeout — **accepted**
  - reviewed commit: `78a9a2bbf3a14329a26b42b333cdce492c4eee96`
  - review: `.agents/handoff/reviews/DLK-M3-020-review.md`
  - closes the DLK-M3-019 correction chain
  - task: `.agents/handoff/tasks/DLK-M3-020-recovery-verification-closeout.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-019`

## Not released

The recovery-verification prerequisite is cleared. These areas still require planning and a released task:

- resolved-issue recurrence reporting (`RECURRED`)
- report generation
- image/CV integration
- LLM integration
- historical-case retrieval
- frontend recovery/verification integration

No new task is currently released for implementation.
