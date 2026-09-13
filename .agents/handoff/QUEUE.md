# Implementation Queue

## Current milestone

Adaptive investigation — durable technician answer submission

## Accepted prerequisites

- Member 2 question-answer contract — merged to synchronized `main`
  - Q01-Q15 answer semantics aligned with knowledge definitions
  - UNKNOWN / NOT_APPLICABLE semantics available
  - answer-driven diagnosis revision workflow available

- `DLK-M3-011` — question-answer persistence and immutable analysis revision append — **accepted**
  - accepted commit: `f242cba7bbfd9521f5e7f497894a22477307b6b3`
  - acceptance was recorded in the ChatGPT review; no separate review file was created under the user's current review preference

## Implemented (awaiting review)

- `DLK-M3-012` — Technician question-answer submission API — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-012-question-answer-api.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-011`

## Not released

Blocked until DLK-M3-012 is implemented and accepted:

- troubleshooting-check result submission
- troubleshooting outcome → evidence integration
- cause confirmation workflow
- issue recovery verification
- report generation
- image/CV integration
- LLM integration
- historical-case retrieval
- frontend adaptive-answer integration

Before releasing troubleshooting-check APIs, planner must re-check Member 2's current check/action outcome mappings.

Only DLK-M3-012 is authorized for implementation.
