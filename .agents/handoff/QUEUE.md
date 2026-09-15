# Implementation Queue

## Current milestone

Explicit root-cause confirmation

## Accepted prerequisite

- `DLK-M3-016` — Final check-result rollback/exact-state verification — **accepted**
  - reviewed commit: `a262a22305e70d47fd40a66e6e7abd1b48d19a16`
  - closes the DLK-M3-013 through DLK-M3-016 troubleshooting-check correction chain

## Ready

- `DLK-M3-017` — Explicit durable root-cause confirmation workflow — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-017-cause-confirmation-api.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-016`

## Not released

Blocked until DLK-M3-017 is implemented and accepted:

- issue recovery / post-correction verification
- resolved / recurred state workflow
- report generation
- image/CV integration
- LLM integration
- historical-case retrieval
- frontend confirmation integration

Only DLK-M3-017 is authorized for implementation.
