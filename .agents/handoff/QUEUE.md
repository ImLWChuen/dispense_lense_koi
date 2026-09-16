# Implementation Queue

## Current milestone

Durable case report/export

## Accepted prerequisite

- `DLK-M3-021` — Durable resolved-issue recurrence reporting workflow — **accepted**
  - reviewed commit: `ff8a4d9ccaef2f7be2dc539c77cf4c46d963739f`

## Ready

- `DLK-M3-022` — Deterministic durable case report export API — **implemented**
  - reviewed commit: `c445855a03ee165db2a05540931c72bb801b014f`
  - review: `.agents/handoff/reviews/DLK-M3-022-review.md`
  - corrections: consistent report revision basis, failure-path nonmutation proof, and accurate verification/report documentation.
  - task: `.agents/handoff/tasks/DLK-M3-022-case-report-export.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-021`

## Not released

Blocked until DLK-M3-022 is accepted:

- PDF/document rendering
- historical-case retrieval / similarity
- LLM explanation/report narration
- image/CV integration
- frontend report integration

Only DLK-M3-022 is authorized for implementation.
