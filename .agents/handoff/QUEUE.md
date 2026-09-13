# Implementation Queue

## Current milestone

Backend/database integration — durable diagnosed-case API

## Accepted prerequisite

- `DLK-M3-008` — Effective test-destination safety closeout — **accepted**
  - accepted commit: `2ff7a8be5a93fc88dac5954b306ed1436c73ceda`
  - closes the DLK-M3-006 / 007 / 008 persistence-review chain

## Changes requested

- `DLK-M3-009` — Durable diagnosed-case create/retrieve API — **changes_requested**
  - task: `.agents/handoff/tasks/DLK-M3-009-durable-case-api.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-008`

  - review: `.agents/handoff/reviews/DLK-M3-009-review.md`
  - reviewed commit: `468ee3d311db7bcea114f580e28539602a91967b`

## Implemented (awaiting review)

- `DLK-M3-010` — Durable case verification closeout — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-010-durable-case-verification-closeout.md`
  - branch: `backend-database`
  - corrects DLK-M3-009; no new application features are released.

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

Only DLK-M3-010 is authorized for implementation. Remote Git operations remain prohibited without explicit user instruction.
