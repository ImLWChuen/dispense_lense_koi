# Implementation Queue

## Current milestone

Troubleshooting-check workflow closeout

## Review state

- `DLK-M3-013` — Check-result semantic closeout and durable troubleshooting-check result API — **changes_requested**
  - reviewed commit: `5e7cb8270762f0e0c06a0c994a0fa424f16f9c2a`
  - review: `.agents/handoff/reviews/DLK-M3-013-review.md`
  - blockers:
    - reject `PENDING` / `IN_PROGRESS` before evidence/persistence
    - prove rollback after actual pending/flushed writes

## Ready

- `DLK-M3-014` — Troubleshooting-check result closeout — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-014-check-result-closeout.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-013`

## Not released

Blocked until DLK-M3-014 is accepted:

- explicit cause-confirmation persistence/API
- issue recovery verification
- report generation
- image/CV integration
- LLM integration
- historical-case retrieval
- frontend check-result integration

Only DLK-M3-014 is authorized for implementation.
