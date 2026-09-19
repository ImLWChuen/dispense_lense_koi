# Implementation Queue

## Current milestone

Phase 1: calibrated vision and evidence-safety foundation

## Ready current task

- `DLK-M3-026` — Calibrated vision and evidence-safety foundation — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-026-calibrated-vision-evidence-foundation.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-025`
  - outcome: calibrated and resolution-independent image features, canonical score-bearing observations only with explicit comparison basis, lossless metadata persistence, safe mixed evidence, and provenance-aware bounded explanations
  - review stop: do not begin frontend Phase 2 until this task is implemented and accepted
  - explicit exclusions: frontend changes, D06 score-bearing classification, knowledge/weight changes, lifecycle changes, image/blob storage, remote Git operations

## Accepted current task

- `DLK-M3-025` — Restore safe backend startup and offline troubleshooting baseline — **accepted**
  - reviewed commit: `f1db85435b177dd9961a14116900c03556a912de`
  - verification: Gemini reports 401 backend tests passed; reviewer source review, task validation and committed whitespace checks passed; no independent backend rerun
  - review: `.agents/handoff/reviews/DLK-M3-025-review.md`
  - corrections addressed (R1–R7): restored migration environment via try/finally; isolated offline tests from real .env loading and shell overrides; exercised mocked provider timeout and error paths with exact deterministic parity assertions; rejected ambiguous development database destinations before rebinding; preserved in-process TestClient requests while blocking outbound transport; exercised actual production .env loader in isolation; gated migrations behind exit-code checked validation; verified development database nonmutation via table counts and sample identity checks
  - task: `.agents/handoff/tasks/DLK-M3-025-backend-runtime-offline-safety.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-024`
  - outcome: synchronized declared dependencies, deterministic no-key operation, frontend port-3001 CORS, and a separate fail-closed PostgreSQL test destination that preserves development records
  - explicit exclusions: image/CV work, check-history repair, diagnostic semantic changes, frontend edits, schema/migration changes, and remote Git operations

## Deferred after the calibrated-vision programme

- Canonical lossless check-history integrity — **planned, not released**
  - preserve stored check outcome, provenance, notes, and revision consistently across case responses and reports;
  - retain compatibility with the teammate check-execution projection;
  - cover legacy canonical records that do not yet have a projection;
  - assign a new task ID only after the active calibrated-vision task is reviewed.

## Integration accepted (R4 and R5 resolved)

- Reviewed reconciliation commit: `c7a21a8f4e670a653f49cef8958b07d958d8b185`; accepted by ChatGPT review.
- R5 resolved: returned persisted nested `analysis_revision` snapshots in `POST /checks`, exactly as `GET` handler does, retaining revision bound (`<= target_revision`). Preserved `changes_from_previous` and `new_evidence_summary`. Added `test_check_execution_analysis_revision_history_parity` verifying complete history objects parity against fresh GET and PostgreSQL snapshots.
- R4 resolved: reconciled `/checks` with canonical engine and persistence contracts; added `get_case_check_executions`, synchronized `CheckExecutionModel` in `append_check_result_revision`, added alias support in `get_action_by_id`, ensured single commit on successful response construction, and added real PostgreSQL integration test suite (`test_check_execution_api.py`).
- Review: `.agents/handoff/reviews/DLK-M3-024-review.md` (R4 & R5 resolution sections added).
- Full backend suite independently verified by reviewer on 2026-09-16: 350 passed, 0 failed, 34 warnings. Previously authorized publication may proceed.

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

The earlier competition-critical Member 3 backend MVP milestone was accepted. `DLK-M3-026` now starts the separately approved calibrated-vision programme. Member 1 integration follow-up remains documented in `docs/api/frontend-backend-contract.md`; any new backend integration defect requires a bounded follow-up task.
