# Implementation Queue

## Current milestone

Downloadable case report rendering

## Accepted prerequisite

- `DLK-M3-022` — Deterministic durable case report export API — **accepted**
  - reviewed commit: `e68015c4587b5f5afe7b14e78b2fe161dd3bf40c`

## Accepted

- `DLK-M3-023` — Deterministic downloadable PDF case report — **accepted**
  - reviewed commit: `53cc609ad136628a811d6291522ae64c7ff70f72`
  - review: `.agents/handoff/reviews/DLK-M3-023-review.md`
  - accepted evidence: section-scoped multi-row history verification, negative reversed/mismatched-row proof, deterministic persisted timestamps, complete diagnosis evidence, visual layout report, and neutral provenance text.
  - task: `.agents/handoff/tasks/DLK-M3-023-pdf-report-export.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-022`
  - dependency authorization:
    - `reportlab==5.0.1` — production renderer
    - `pypdf==6.18.1` — parser/text-validation dependency
    - no other PDF dependency or native renderer is authorized

## Not released

No follow-on task is currently authorized. Remaining roadmap areas include:

- historical-case retrieval / similarity
- LLM explanation/report narration
- image/CV integration
- frontend report integration

DLK-M3-023 is complete. A new bounded task must be authorized before further implementation.
