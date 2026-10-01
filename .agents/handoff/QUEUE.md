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

- `DLK-M3-033` — Preserve region inspection reliability — **accepted**
  - reviewed commit: `3d1fb6f5adb6d50a975704527f21f23334549546`
  - review: `.agents/handoff/reviews/DLK-M3-033-review.md`
  - resolved correction R1: moved expected-but-omitted ROI warning collection outside nonempty measurement branches with empty/None list safety; collected all applicable current/reference region reliability reasons into top-level warnings before early returns; preserved FEATURES_ONLY as UNCALIBRATED with no observations; preserved calibrated whole-image UNRELIABLE gates; added regressions for real uniform FEATURES_ONLY upload, multiple unassessed reference regions, simultaneous current/reference failures, and empty current/reference measurement lists with populated unassessed IDs; verified focused suite (66 passed) and full backend suite (529 passed)
  - task: `.agents/handoff/tasks/DLK-M3-033-region-inspection-reliability.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-032`; integrated baseline `a4cb267`
  - authorized scope: additive per-region inspection statuses and warnings; distinguish unassessed from missing; trustworthy aggregates; conservative classification gates; regression tests and API documentation
  - deferred: partial score-bearing analysis, overlays, template storage, automatic site detection/alignment, frontend changes
  - planning roadmap: `docs/architecture/region-inspection-improvement-plan.md`
  - inspection layout decision remains pending and does not block this foundation task

## Active task

- `DLK-M3-034` — Expose bounded deposit outlines for trustworthy region overlays — **accepted**
  - reviewed commit: `7a55e65f4f3ad3a733289393f6f5a832ba47db52`
  - review: `.agents/handoff/reviews/DLK-M3-034-review.md`
  - resolved correction R1: rejected nonconsecutive duplicate polygon vertices after normalization with specific overlay warning `ROI '{roi_id}' deposit outline unavailable (nonconsecutive duplicate vertices detected).`; preserved DETECTED region status and diagnostic observations; added unit and integration regressions; synchronized queue state with implementation report
  - task: `.agents/handoff/tasks/DLK-M3-034-bounded-deposit-outline.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-033` at `3d1fb6f5adb6d50a975704527f21f23334549546`
  - outcome: optional full-image normalized outer contour geometry for reliable detected deposits, with bounded size, strict vertex distinctness, and explicit omission warnings
  - deferred: frontend overlays, templates/alignment, partial evidence, database changes

## Active task

- `DLK-M3-035` — Preserve every affected region ID in deduplicated image observations — **accepted**
  - reviewed commit: `2977003e72b8a8fd9a3697a95c543f3ce5465b31`
  - review: `.agents/handoff/reviews/DLK-M3-035-review.md`
  - resolved corrections R1/R2: clarified in api-spec.md that affected ROI lists are exact per observation and may overlap across different rules; corrected task report to clarify unmatched reference sites are skipped with warning while UNASSESSED sites retain the whole-image gate; marked supported acceptance checkboxes
  - task: `.agents/handoff/tasks/DLK-M3-035-affected-region-provenance.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-034` at `7a55e65f4f3ad3a733289393f6f5a832ba47db52`
  - outcome: one observation per defect type/value with ordered unique affected ROI IDs in metadata; same scoring contribution and durable case round-trip
  - deferred: frontend display, Member 2 scoring/interpretation changes, partial evidence, templates/alignment

## Active task

- `DLK-M3-036` — Expose truthful expected-site inspection coverage — **accepted**
  - task: `.agents/handoff/tasks/DLK-M3-036-inspection-coverage-summary.md`
  - reviewed commit: `86ae4ffd764213503e9e2dac6dbbe0c72784525c`
  - review: `.agents/handoff/reviews/DLK-M3-036-review.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-035` at `2977003e72b8a8fd9a3697a95c543f3ce5465b31`
  - authorized outcome: additive current-image expected/assessed site counts and complete/partial/none inspection coverage, with unknown defaults for legacy aggregates
  - preserve: current conservative zero-observation gate for partially unassessed calibrated images, diagnostic scoring, frontend behavior, and reference-image safety
  - deferred: partial score-bearing evidence, frontend display, reusable layouts/alignment, and reference coverage reporting

## Active task

- `DLK-M3-037` — Expose reference-image inspection coverage separately — **accepted**
  - task: `.agents/handoff/tasks/DLK-M3-037-reference-inspection-coverage.md`
  - reviewed commit: `a124dbcd5a6cd58c54f0435c548bdf95348e9442`
  - review: `.agents/handoff/reviews/DLK-M3-037-review.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-036` at `86ae4ffd764213503e9e2dac6dbbe0c72784525c`
  - authorized outcome: return the already calculated reference aggregate as an optional, separately scoped API field in reference-image mode
  - preserve: existing current-image aggregate, conservative reference gate, observation eligibility and score, and Member 1 frontend ownership
  - deferred: reference alignment, partial score-bearing evidence, frontend workbench, and reusable profiles

## Active task

- `DLK-M3-038` — Establish a repeatable synthetic region-inspection baseline — **accepted**
  - task: `.agents/handoff/tasks/DLK-M3-038-synthetic-region-inspection-baseline.md`
  - reviewed commit: `899d36d64e7d04f0734423eb190b872fb2ac4d77`
  - review: `.agents/handoff/reviews/DLK-M3-038-review.md`
  - resolved corrections R1/R2/R3: added per-case elapsed_seconds and focused coverage; corrected Python version and verified reproduction commands; updated documented JSON output; executed full backend test suite against disposable test database (578 passed, 42 warnings in 59.67s) and recorded in task report
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-037` at `a124dbcd5a6cd58c54f0435c548bdf95348e9442`
  - authorized outcome: deterministic labeled synthetic fixture manifest, offline region-inspection benchmark, measured baseline report
  - preserve: production CV/API/diagnosis behavior and existing safety gates; no industrial-accuracy claim from synthetic data
  - deferred: real-image evaluation, numerical acceptance targets, partial score-bearing evidence, Member 1 visual workbench, reusable profiles/alignment

## Active task

- `DLK-M3-039` — Preserve per-region measurements and limits in image evidence — **accepted**
  - reviewed commit: `641328c0210cd31b56a50717792958fd39886bd3`
  - review: `.agents/handoff/reviews/DLK-M3-039-review.md`
  - task: `.agents/handoff/tasks/DLK-M3-039-per-region-evidence-snapshots.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-038` at `899d36d64e7d04f0734423eb190b872fb2ac4d77`
  - outcome: additive per-site measurement snapshots and supplied limits in existing observation metadata, preserved through durable cases
  - preserve: observation identity/order, affected-site membership, diagnostic scores, conservative gates, and legacy metadata
  - deferred: frontend workbench, partial evidence, report rendering, profiles/alignment, and real-image accuracy evaluation
  - verification: focused suite 82 passed; full backend suite 587 passed; task validation VALID; whitespace checks passed
  - accepted DLK-M3-038 review included in the implementation commit

## Active task

- `DLK-M3-040` — Include persisted region evidence in case reports — **implemented**
  - reviewed commit: `9a8e2a53270e61d7060a6342d0ee6f25a7abdf1a`
  - review: `.agents/handoff/reviews/DLK-M3-040-review.md`
  - resolved corrections:
    - R1: bounded all PDF metadata presentation paths (20 affected IDs chunked 4/row with explicit omission counts; strictly allowlisted 21 limit keys with finite scalar validation chunked 3/row; strict `_fmt_num` and `_fmt_bool` treating non-finite/invalid scalars as `unavailable`; user strings bounded at 200 chars);
    - R2: preserved missing/unknown scope as `Not recorded or unknown`; read canonical `roi_id` and nested `current_measurements.inspection_status` validated against enum `DETECTED`/`MISSING`/`UNASSESSED` (rendering non-enum statuses as `UNKNOWN`); included reference `has_bubbles` display; updated positive test fixtures to canonical contract; added regressions for missing scope, conflicting aliases, non-enum status, and malformed scalar fields; added stress test combining 50 long canonical ROI IDs, 60 affected IDs, nested limits, and invalid numeric fields; added real `_sync_analyze_image`-to-case-to-JSON/PDF scenario (`test_real_image_analysis_to_case_to_report_and_pdf`)
  - task: `.agents/handoff/tasks/DLK-M3-040-region-evidence-case-reports.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-039` at `641328c0210cd31b56a50717792958fd39886bd3`
  - outcome: revision-scoped image observations in JSON reports and bounded readable region evidence in standard PDF reports
  - preserve: read-only report assembly, pinned revision, diagnostic/lifecycle meaning, existing routes and legacy compatibility
  - deferred: frontend workbench, partial evidence, reusable profiles/alignment, real-image evaluation, and 8D report changes
  - verification: focused suite 38 passed; full backend suite 599 passed; task validation VALID; whitespace checks passed
  - accepted DLK-M3-039 review included in the implementation commit

Earlier milestone completion statements describe the previous submission scope. Remote Git operations still require explicit user instruction.
