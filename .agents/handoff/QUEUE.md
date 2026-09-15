# Implementation Queue

## Current milestone

Resolved-issue recurrence reporting

## Accepted prerequisite

- `DLK-M3-020` — Recovery-verification workflow closeout — **accepted**
  - reviewed commit: `78a9a2bbf3a14329a26b42b333cdce492c4eee96`

## Ready

- `DLK-M3-021` — Durable resolved-issue recurrence reporting workflow — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-021-recurrence-api.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-020`

## Not released

Blocked until DLK-M3-021 is accepted:

- report generation / case export
- image/CV integration
- LLM integration
- historical-case retrieval
- frontend recurrence integration

Only DLK-M3-021 is authorized for implementation.
