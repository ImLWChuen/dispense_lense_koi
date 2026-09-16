# Implementation Queue

## Current milestone

Final backend MVP acceptance and contract hardening

## Integration changes requested (R4 resolved)

- Reviewed reconciliation commit: `3be96cceaa56b0f4700fa252dba18f1f877dd89a`.
- R4 resolved: reconciled `/checks` with canonical engine and persistence contracts; added `get_case_check_executions`, synchronized `CheckExecutionModel` in `append_check_result_revision`, added alias support in `get_action_by_id`, ensured single commit on successful response construction, and added real PostgreSQL integration test suite (`test_check_execution_api.py`).
- Review: `.agents/handoff/reviews/DLK-M3-024-review.md` (R4 resolution section added).
- Full backend suite verified: 349 passed, 0 failed.

## Accepted prerequisite

- `DLK-M3-023` — Deterministic downloadable PDF case report — **accepted**
  - reviewed commit: `53cc609ad136628a811d6291522ae64c7ff70f72`
  - recorded full backend verification: 297 passed, 0 failed, 0 skipped
  - PDF unit verification: 5 passed
  - PDF integration verification: 9 passed

## Accepted

- `DLK-M3-024` — Final backend MVP contract and end-to-end acceptance — **accepted**
  - reviewed commit: `2f60f9292b07edfe6982996e1d10cdfe84d48d66`
  - review: `.agents/handoff/reviews/DLK-M3-024-review.md`
  - corrections: genuine empty-list integration proof with transactional isolation and rollback, failure-path and asserted revision 7 rich-state nonmutation proof, accurate Member 1 contract documentation.
  - task: `.agents/handoff/tasks/DLK-M3-024-backend-mvp-acceptance.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-023`
  - primary nature: verification/hardening, not a new diagnostic feature

## Explicitly deferred

Do not release these within DLK-M3-024:

- vector/semantic historical-case retrieval
- bounded LLM integration
- image/CV integration
- analytics
- authentication/authorization
- frontend implementation

The scoped competition-critical Member 3 backend milestone is accepted. No task is currently ready. Member 1 integration follow-up remains documented in `docs/api/frontend-backend-contract.md`; any new backend integration defect requires a bounded follow-up task.
