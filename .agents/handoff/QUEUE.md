# Implementation Queue

## Current milestone

Troubleshooting-check workflow verification closeout

## Review state

- `DLK-M3-013` — Check-result semantic closeout and durable troubleshooting-check result API — **changes_requested**
  - review: `.agents/handoff/reviews/DLK-M3-013-review.md`
  - implementation chain remains blocked by verification closeout

- `DLK-M3-014` — Troubleshooting-check result closeout — **changes_requested**
  - review: `.agents/handoff/reviews/DLK-M3-014-review.md`
  - production unfinished-state correction is resolved
  - remaining concerns are verification-only

- `DLK-M3-015` — Check-result verification closeout — **changes_requested**
  - reviewed commit: `9ad094cfa3b56e3042996238ce4acc0752f9f98c`
  - review: `.agents/handoff/reviews/DLK-M3-015-review.md`
  - remaining gaps:
    - rollback baselines need nonempty prior check history
    - snapshot helper must preserve exact empty-string vs NULL values
    - rollback hooks must capture complete pending revision `result_snapshot`

## Ready

- `DLK-M3-016` — Final check-result verification closeout — **in_progress**
  - task: `.agents/handoff/tasks/DLK-M3-016-check-result-verification-final-closeout.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-015`
  - scope: test-only; no production-code changes

## Not released

Blocked until DLK-M3-016 is implemented and accepted and the DLK-M3-013 correction chain is closed:

- explicit cause-confirmation persistence/API
- issue recovery verification
- report generation
- image/CV integration
- LLM integration
- historical-case retrieval
- frontend check-result integration

Only DLK-M3-016 is authorized for implementation.
