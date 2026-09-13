# Implementation Queue

## Current milestone

Backend/database integration — adaptive investigation persistence foundation

## Accepted prerequisite

- `DLK-M3-010` — Durable case verification closeout — **accepted**
  - accepted commit: `d94e8ea54837719a444a27af05f2eac71efcb34f`
  - acceptance was recorded in the ChatGPT review; no review file was created under the user's current review preference
  - closes the durable initial-case create/retrieve verification chain

## Implemented (awaiting review)

- `DLK-M3-011` — Persist follow-up question answers and append immutable analysis revisions — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-011-question-answer-persistence.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-010`

## Explicit ownership gate

Member 2 owns question meaning and answer-to-evidence mappings. Current inspection shows the repository's `QuestionAnswerHandler` mapping is not aligned with every question in `knowledge/questions.json`. DLK-M3-011 therefore establishes persistence/reconstruction and revision append behavior only; it must not expose a technician-facing arbitrary-answer endpoint or modify Member 2 logic.

## Not released

Blocked until DLK-M3-011 is accepted and Member 2 answer semantics are aligned/approved:

- public question-answer submission API;
- troubleshooting-check result persistence/API;
- explicit cause confirmation;
- recovery verification;
- reports
- image/CV
- LLM integration
- historical-case retrieval
- frontend follow-up workflow integration.

Only DLK-M3-011 is authorized for implementation. Remote Git operations remain prohibited without explicit user instruction.
