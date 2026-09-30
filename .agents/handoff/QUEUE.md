# Implementation Queue

## Current milestone

Finalist image inspection improvements: trustworthy region-level results

## Accepted prerequisite

- `DLK-M3-030` — Final submission hardening and end-to-end demo acceptance — **accepted**
  - reviewed commit: `747235695fa9777a8b9f84f4b47e66844b50a98f`
  - accepted outcome: calibrated image-to-diagnosis-to-lifecycle-to-report/dashboard flow, truthful dynamic surfaces, deterministic evidence-projected AI summaries, clean frontend lint/build, and 491 passing backend tests
  - review: `.agents/handoff/reviews/DLK-M3-030-review.md`
  - next-stage evidence: root startup documentation and the existing database helper are still environment-specific/inaccurate, so repeatable local demo operation remains a release dependency

## Accepted startup task

- `DLK-M3-031` — Repeatable local demo startup and operator runbook — **accepted**
  - task: `.agents/handoff/tasks/DLK-M3-031-local-demo-readiness.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-030`
  - implemented outcome:
    - portable/safe PostgreSQL startup script (`scripts/start-db.ps1`) without hardcoded paths, waiting for health check and preserving development volume;
    - read-only environment preflight script (`scripts/demo-preflight.ps1`) checking tools, dependencies, non-blank config presence, and port availability (8000/3001) without killing processes;
    - post-startup identity verification script (`scripts/verify-demo.ps1`) confirming `dispense-lens-api` and `DispenseIQ` frontend and rejecting wrong local applications;
    - rewritten root `README.md` with complete three-layer quickstart, Node.js 20.9.0+ requirement, port 3001 instructions, port 3000 avoidance warning, health scope, and troubleshooting;
    - competition demo runbook (`docs/demo/local-demo-runbook.md`) with 6–10 minute timed walkthrough, truthful claims, failure fallbacks, and rehearsal tracking;
    - resolved review findings R1–R5:
      - R1: rewrote timed runbook using only rendered controls and ordering from the checked-in UI (image analysis on `/diagnosis/new` before Start Diagnosis, Dispensing Line A, blockage_found, free-text recovery/boolean verification, no static score or ranking claims);
      - R2: replaced confidence-percentage, probability, and Bayesian terminology with the accepted deterministic `Evidence Support /100` meaning across README, runbook, and task packet;
      - R3: enforced Node.js `>=20.9.0` requirement in README and preflight (`Test-NodeVersionSupported`); verified across lower, exact, and higher versions;
      - R4: ensured secret-safe database check (`Get-DatabaseConfigStatus`) strictly rejecting missing and blank `DATABASE_URL` values without leaking connection strings or credentials; verified missing, blank, and configured branches;
      - R5: aligned runbook labels with exact rendered UI controls (`Analyze`, `Evidence`, `Submit Check Result`, `Submit Passed Verification` / `Submit Failed Verification`); explicitly prefixed all entered symptom, material, check, recovery, and verification details with `[SYNTHETIC DEMO]`; removed nonexistent editable operator example and explained generic technician actor.
  - verification: PowerShell AST parse (3/3 passed), Node-version checks (below/exact/above verified), secret-safe database checks (missing/blank/configured verified), static runbook terminology & UI label check (clean), health API test passed (2/2), frontend lint (0 errors, 0 warnings), frontend build (13/13 routes), task validation (VALID), git diff whitespace check passed;
  - reviewed commit: `ececf645938dc910721655af55df8ae8a3ce5cef`
  - review: `.agents/handoff/reviews/DLK-M3-031-review.md`
  - next step: Member 3 feature implementation is complete for the authorized scope; proceed with final team rehearsal, submission evidence/video, and user-directed Git publication or merge

## Accepted rehearsal correction

- `DLK-M3-032` — Consolidate analytics defects by canonical code — **accepted**
  - reviewed commit: `01640a7fb3344d49a3dedc478d75ad3bc7f1d475`
  - accepted outcome: recognized codes, including `D03_INCONSISTENT_SIZE`, are consolidated into one canonical analytics entry; null-code categories remain intact; unknown non-null codes use deterministic code-derived labels
  - verification: focused analytics suite `16 passed`; full backend suite `507 passed`; whitespace checks passed
  - review: `.agents/handoff/reviews/DLK-M3-032-review.md`
  - next step: restart the local backend before browser verification, then continue final rehearsal; no separate next-feature task is authorized

## Explicitly deferred

Do not implement inside DLK-M3-031:

- vector/semantic historical-case similarity
- new AI/CV models
- D06 score-bearing vision semantics
- authentication/authorization
- new analytics infrastructure
- deployment redesign or production hosting
- new testing frameworks
- database/schema changes

## Active task

- `DLK-M3-033` — Preserve region inspection reliability — **implemented**
  - reviewed commit: `028c85740175451940fd01837b7e87f479329e01`
  - review: `.agents/handoff/reviews/DLK-M3-033-review.md`
  - resolved correction R1: moved expected-but-omitted ROI warning collection outside nonempty measurement branches with empty/None list safety; collected all applicable current/reference region reliability reasons into top-level warnings before early returns; preserved FEATURES_ONLY as UNCALIBRATED with no observations; preserved calibrated whole-image UNRELIABLE gates; added regressions for real uniform FEATURES_ONLY upload, multiple unassessed reference regions, simultaneous current/reference failures, and empty current/reference measurement lists with populated unassessed IDs; verified focused suite (66 passed) and full backend suite (529 passed)
  - task: `.agents/handoff/tasks/DLK-M3-033-region-inspection-reliability.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-032`; integrated baseline `a4cb267`
  - authorized scope: additive per-region inspection statuses and warnings; distinguish unassessed from missing; trustworthy aggregates; conservative classification gates; regression tests and API documentation
  - deferred: partial score-bearing analysis, overlays, template storage, automatic site detection/alignment, frontend changes
  - planning roadmap: `docs/architecture/region-inspection-improvement-plan.md`
  - inspection layout decision remains pending and does not block this foundation task

The user authorized the first finalist image-improvement task. Execute only DLK-M3-033, then return for review. Earlier milestone completion statements describe the previous submission scope; they do not block this newly authorized task. Remote Git operations still require explicit user instruction.
