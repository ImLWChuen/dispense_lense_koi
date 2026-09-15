# Implementation Queue

## Current milestone

Cause-confirmation workflow closeout

## Review state

- `DLK-M3-017` — Explicit durable root-cause confirmation workflow — **changes_requested**
  - reviewed commit: `d15c080b532cdbb03b62f81d910e8d41b83e7771`
  - blockers:
    - sanitize unexpected engine `ValueError`s as HTTP 500
    - enforce `confirmed_by` maximum length 64 at request validation

## Ready

- `DLK-M3-018` — Cause-confirmation API closeout — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-018-cause-confirmation-closeout.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-017`

## Not released

Blocked until DLK-M3-018 is implemented and accepted:

- issue recovery / post-correction verification
- resolved / recurred state workflow
- report generation
- image/CV integration
- LLM integration
- historical-case retrieval
- frontend cause-confirmation integration

Only DLK-M3-018 is authorized for implementation.
