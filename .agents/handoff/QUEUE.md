# Implementation Queue

## Current milestone

Downloadable case report rendering

## Accepted prerequisite

- `DLK-M3-022` — Deterministic durable case report export API — **accepted**
  - reviewed commit: `e68015c4587b5f5afe7b14e78b2fe161dd3bf40c`

## Ready

- `DLK-M3-023` — Deterministic downloadable PDF case report — **implemented**
  - reviewed commit: `07abe45aaf56f52fc1bad918277bfb689b17b03b`
  - review: `.agents/handoff/reviews/DLK-M3-023-review.md`
  - corrections: deterministic persisted timestamps, complete diagnosis evidence, history count/order proof, visual layout verification, and neutral provenance text.
  - task: `.agents/handoff/tasks/DLK-M3-023-pdf-report-export.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-022`
  - dependency authorization:
    - `reportlab==5.0.1` — production renderer
    - `pypdf==6.18.1` — parser/text-validation dependency
    - no other PDF dependency or native renderer is authorized

## Not released

Blocked until DLK-M3-023 is accepted:

- historical-case retrieval / similarity
- LLM explanation/report narration
- image/CV integration
- frontend report integration

Only DLK-M3-023 is authorized for implementation.
