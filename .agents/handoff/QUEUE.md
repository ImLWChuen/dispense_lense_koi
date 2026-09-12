# Implementation Queue

## Current milestone

Backend/database integration — durable diagnosed-case API

## Accepted prerequisite

- `DLK-M3-008` — Effective test-destination safety closeout — **accepted**
  - accepted commit: `2ff7a8be5a93fc88dac5954b306ed1436c73ceda`
  - closes the DLK-M3-006 / 007 / 008 persistence-review chain

## Implemented (awaiting review)

- `DLK-M3-009` — Durable diagnosed-case create/retrieve API — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-009-durable-case-api.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-008`

## Not released

Blocked until DLK-M3-009 is implemented and accepted:

- follow-up answer submission and later analysis revisions
- troubleshooting-check outcome submission
- cause confirmation
- issue recovery verification
- reports
- image/CV
- LLM integration
- historical-case retrieval
- frontend durable-case integration

Only DLK-M3-009 is authorized for implementation.
