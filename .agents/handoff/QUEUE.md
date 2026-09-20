# Implementation Queue

## Current milestone

Phase 3B: restart-safe technician troubleshooting and lifecycle workflow

## Active task

- `DLK-M3-029` — Restart-safe technician troubleshooting and lifecycle workflow — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-029-technician-lifecycle-workflow.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-028`
  - outcome: make questions, physical checks, cause confirmation, recovery action, recovery verification, and recurrence truthful, independent, revision-safe, and resumable after refresh or partial failure
  - authorized backend contract: additive confirmation and lifecycle histories in `GET /api/v1/cases/{case_id}` only; no database or diagnostic-semantic changes
  - protected overlap: do not modify or stage the existing uncommitted `frontend/app/(dashboard)/cases/[id]/page.tsx`
  - review stop: return to ChatGPT after one local implementation commit; do not begin final end-to-end acceptance or remote Git operations
  - review: `.agents/handoff/reviews/DLK-M3-029-review.md`
  - reviewed commit: `3ed257979602d6afbc84fd8cac5fd33bbedca821`
  - corrections resolved (R1–R7): preserve mutation failures and technician form inputs while refreshing durable state; never reactivate historical checks when no next check exists (resolveActiveCheck returns undefined for all-historical lists); render PASSED/FAILED badges only when verification_passed is boolean and restricted to recovery-verification events; expose all 6 check execution statuses (COMPLETED, BLOCKED, SKIPPED, FAILED, UNKNOWN, NOT_APPLICABLE) with safe UNKNOWN finding and omitted outcome for non-completed checks; require non-blank verification details for both passed and failed recovery verifications; fetch authoritative durable case on mutation success to prevent history erasure; canonical no_blockage outcome key used for ACT01; strengthened 14-scenario dependency-free regression test-diagnostic-workflow-state.mjs covering all production helpers and mutation state paths
  - reviewer verification: 89 focused backend tests and 481 full backend tests passed; 14 workflow regressions passed; focused task-owned ESLint passed; production build and task validation passed; full repository lint still fails on unrelated/pre-existing files and must be reported accurately
  - next step: return to ChatGPT for review; do not create a new task packet, touch protected/unrelated files, push, merge, or begin final end-to-end acceptance
  - explicit exclusions: diagnostic engine/knowledge/weights, durable rejection semantics, migrations, image workflow, dashboard/analytics/reports, authentication, dependencies, deployment, protected case-detail integration, and remote Git operations

## Accepted Phase 3A dependency

- `DLK-M3-028` — Truthful dynamic dashboard, reports, analytics, and evidence-support labels — **accepted**
  - task: `.agents/handoff/tasks/DLK-M3-028-truthful-dynamic-demo-surfaces.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-027`
  - outcome: remove fabricated analytics/report fallbacks, derive workflow metrics from persisted data, present deterministic scores as Evidence Support /100, and make dashboard/case/report/analytics states truthful
  - protected overlap: do not touch the existing uncommitted `frontend/app/(dashboard)/cases/[id]/page.tsx`
  - review stop: return to ChatGPT after the local implementation commit; do not begin Phase 3B lifecycle corrections
  - review: `.agents/handoff/reviews/DLK-M3-028-review.md`
  - corrections resolved (R1–R7): comparable trend cohorts (dashboard operational trends return null); first-time resolution derived strictly from explicit verification lifecycle events (ignores revisions, returns null when evidence unsupported); resolution durations measure only cases with persisted resolution events (excluded from buckets, nullable averages); mutually exclusive loading, error, empty, and data states in dashboard, analytics, and reports (initial failure displays dedicated error card, refresh failure retains data with stale banner); canonical `machine_context.equipment` key read alongside compatibility keys; distinct case counts in cause distributions via `func.distinct(case_id)`; insight trend aligned to `"% of defect-recorded cases"` and defect trend queries cases with defect codes over 6-month window
  - corrections resolved (R8–R11): empty chart arrays instead of zero-filled placeholder rows (`defect_trend=[]` and `resolution_time_distribution=[]` when no observed data); deterministic defect distribution sorting (`count desc, defect_name asc`) and decoupled scoped aggregate insight wording without unwarranted causal or recency claims; nullable defect breakdown code without invented `D00`; reachable reports header refresh button and reload failure state preserving loaded reports with stale warning banner, backed by dependency-free regression suite `test-reports-state.mjs`
  - corrections resolved (R12–R15): resolved report styling and icon derived strictly from `isResolved`; production reports page driven by tested `deriveReportsView` flags without JSX duplication; missing/invalid timestamps return `Not recorded` (never `Recent` or `Invalid Date`); authorized `frontend/lib/reports-state.ts` and `frontend/scripts/test-reports-state.mjs` in Allowed paths
  - reviewed commit: `6e33cf3550d3670d660d731c4e87ed5b6093260a`
  - reviewer verification: all 14 focused PostgreSQL analytics checks passed; 480 full backend tests passed; 9 reports state regression tests passed; 7 image upload regression tests passed; focused ESLint passed with zero findings; production build passed with all 13 static pages generated; task validation and whitespace checks passed
  - next step: return to the planner before publication/integration or beginning Phase 3B
  - explicit exclusions: troubleshooting/check outcomes, cause-confirmation/recovery/verification UI, rejection/exhaustion behavior, protected case-detail integration, dependencies, migrations, authentication, and remote Git operations

## Accepted Phase 2 dependency

- `DLK-M3-027` — Calibrated image workflow and dynamic diagnosis analysis — **accepted**
  - task: `.agents/handoff/tasks/DLK-M3-027-calibrated-image-frontend-workflow.md`
  - review: `.agents/handoff/reviews/DLK-M3-027-review.md`
  - reviewed commit: `ebeacc7d0bb65e42dd4da3c154f43aa0c6adad61`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-026`
  - outcome: typed multipart image client, stable upload/ROI/calibration state, calibrated-only case evidence, persisted image evidence presentation, backend-derived evidence analysis, and canonical new-diagnosis form values
  - corrections resolved (R1–R8): atomic activeRequestToken React state tracking and safe finally cleanup; Section 3.4 observation id contract alignment; backend-guaranteed required response types with separate ObservationInput; lint-clean questions/troubleshooting pages; reproducible verification commands and outputs; shared production module frontend/lib/image-upload-state.ts for pure validation and request-state transitions, imported and executed by ImageUpload.tsx and regression suite with aligned 1.00001 ROI tolerance
  - reviewer verification: shared production state module executed by all seven regression scenarios; focused lint clean across all 17 task-owned frontend files; production build and TypeScript passed; task validation and committed whitespace check passed
  - next step: return to the planner before beginning Phase 3 or publishing this branch
  - explicit exclusions: backend changes, dashboard/reports/cases/analytics, troubleshooting/verification corrections, dependencies, raw image persistence, and remote Git operations

## Accepted calibrated-vision task

- `DLK-M3-026` — Calibrated vision and evidence-safety foundation — **accepted**
  - task: `.agents/handoff/tasks/DLK-M3-026-calibrated-vision-evidence-foundation.md`
  - review: `.agents/handoff/reviews/DLK-M3-026-review.md`
  - reviewed commit: `6e52628f4e6e192a5044dc9de07b0f01b9cdc213`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-025`
  - outcome: calibrated and resolution-independent image features, canonical score-bearing observations only with explicit comparison basis, lossless metadata persistence, safe mixed evidence, and provenance-aware bounded explanations
  - corrections addressed (R1–R9): sanitized internal pipeline failures to 500 without leaking private details; refined target uniformity, border dominance, and candidate ambiguity handling; consistent binary mask arithmetic; strict gating of D04 on explicit presence limit; bounded streaming reads up to 10 MB in 64 KB chunks; strict profile validation (non-empty ProcessLimits, mode exclusivity, unique non-blank roi_id); restored mixed-evidence benchmark intake contract; treated completely uniform frames as UNRELIABLE without an established background/reference basis; documented the actual UNRELIABLE status enum in API specification
  - reviewer verification: 83 focused checks, 37 PostgreSQL workflow/persistence checks, and 466 full backend tests passed; task validation and committed whitespace checks passed
  - next dependency: active `DLK-M3-027`
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
