# Implementation Queue

## Current milestone

Adaptive investigation — durable technician answer submission accepted

## Accepted prerequisites

- Member 2 question-answer contract — merged to synchronized `main`
  - Q01-Q15 answer semantics aligned with knowledge definitions
  - UNKNOWN / NOT_APPLICABLE semantics available
  - answer-driven diagnosis revision workflow available

- `DLK-M3-010` — durable case API rollback and response-parity closeout — **accepted**
  - accepted commit: `d94e8ea54837719a444a27af05f2eac71efcb34f`
  - review: `.agents/handoff/reviews/DLK-M3-010-review.md`

- `DLK-M3-011` — question-answer persistence and immutable analysis revision append — **accepted**
  - accepted commit: `f242cba7bbfd9521f5e7f497894a22477307b6b3`
  - review: `.agents/handoff/reviews/DLK-M3-011-review.md`

- `DLK-M3-012` — technician question-answer submission API — **accepted**
  - accepted commit: `17756205b7299037b5c23a6b97209ac5f594f749`
  - review: `.agents/handoff/reviews/DLK-M3-012-review.md`

## Ready

None. No implementation task is currently released.

## Not released

Pending future task planning and relevant teammate contract checks:

- troubleshooting-check result submission
- troubleshooting outcome → evidence integration
- cause confirmation workflow
- issue recovery verification
- report generation
- image/CV integration
- LLM integration
- historical-case retrieval
- frontend adaptive-answer integration

Before releasing troubleshooting-check APIs, the planner must re-check Member 2's current check/action outcome mappings and explicit human-confirmation semantics.

No further implementation is authorized by this queue.
