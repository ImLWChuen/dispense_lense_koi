# Member 3 integration sequence

Planner snapshot: 2026-09-12, baseline `b953ebf`. Only DLK-M3-004 is executable. Later items are a roadmap, not released task packets; scope and IDs are assigned after review.

| Order | Outcome | Release gate / teammate dependency |
| --- | --- | --- |
| 1: DLK-M3-004, implemented | Initial diagnosis HTTP API plus import compatibility | Member 2 merge gate satisfied. Implementation complete, ready for review. |
| 2: DLK-M3-006, implemented | PostgreSQL persistence contract and minimal case + immutable initial-analysis storage | Implementation complete, ready for review. Real PostgreSQL verified via Docker Compose, Alembic migrations, and integration tests. |
| 3: planned | Create and retrieve a durable diagnosed case through API | Persistence accepted; agree additive request/response and error contract with Member 1. Verify restart durability and atomic writes. |
| 4: planned | Submit one answer and append a new analysis revision | Durable case accepted; verify Member 2 answer semantics and define stale-revision conflict behavior. Previous revisions must remain unchanged. |
| 5: planned | Record check execution/finding and subsequent ranking | Answer flow accepted; Member 2 must resolve any reproduced check-mapping problems before this becomes a technician-facing workflow. |
| 6: planned | Explicit cause confirmation and separate recovery verification | Agree human-confirmation semantics with Member 2; no automatic coupling between a high score, confirmed cause, and issue resolved. |
| 7: planned | One frontend-to-backend walkthrough, then broader coverage | Member 1 has a working diagnosis screen and agreed contract; fix existing frontend build blockers before end-to-end acceptance. |

## Integration gates

- Member 1 can build against the documented initial endpoint after 004 is accepted; it does not provide history, persistence, or follow-up requests yet.
- A teammate merge is not required for independent Member 3 backend work. Shared contract disagreement or overlapping files must be resolved before dependent implementation.
- Main containing the engine establishes availability, not domain correctness. During inspection, `StateManager.evaluate_cause_conclusion` can mark a cause confirmed from a score plus supporting check; the desired explicit technician confirmation needs an owner decision before exposing that flow.
- Inspection also found `ACT02.material_normal` mapping to `MATERIAL_STATE = separated` in the engine. This is an apparent semantic defect requiring a Member 2 reproduction/review before check-result integration. Do not change it in 004.
- The initial API uses keyword extraction currently present in the repository. Live bounded LLM integration remains a separate Member 2 dependency.
- Images, reports, retrieval, and deployment follow the connected core workflow. All six defect categories remain product requirements; image recognition scope is separate.

## Execution policy

Execute one ready packet, return its local commit for ChatGPT review, and wait for the next release. No new push or merge is authorized by this roadmap.
