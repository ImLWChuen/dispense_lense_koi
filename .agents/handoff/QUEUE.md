# Implementation Queue

## Current milestone

Repeatable local demo startup and competition rehearsal readiness

## Accepted prerequisite

- `DLK-M3-030` — Final submission hardening and end-to-end demo acceptance — **accepted**
  - reviewed commit: `747235695fa9777a8b9f84f4b47e66844b50a98f`
  - accepted outcome: calibrated image-to-diagnosis-to-lifecycle-to-report/dashboard flow, truthful dynamic surfaces, deterministic evidence-projected AI summaries, clean frontend lint/build, and 491 passing backend tests
  - review: `.agents/handoff/reviews/DLK-M3-030-review.md`
  - next-stage evidence: root startup documentation and the existing database helper are still environment-specific/inaccurate, so repeatable local demo operation remains a release dependency

## Active task

- `DLK-M3-031` — Repeatable local demo startup and operator runbook — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-031-local-demo-readiness.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-030`
  - implemented outcome:
    - portable/safe PostgreSQL startup script (`scripts/start-db.ps1`) without hardcoded paths, waiting for health check and preserving development volume;
    - read-only environment preflight script (`scripts/demo-preflight.ps1`) checking tools, dependencies, config presence, and port availability (8000/3001) without killing processes;
    - post-startup identity verification script (`scripts/verify-demo.ps1`) confirming `dispense-lens-api` and `DispenseIQ` frontend and rejecting wrong local applications;
    - rewritten root `README.md` with complete three-layer quickstart, port 3001 instructions, port 3000 avoidance warning, health scope, and troubleshooting;
    - competition demo runbook (`docs/demo/local-demo-runbook.md`) with 6–10 minute timed walkthrough, truthful claims, failure fallbacks, and rehearsal tracking;
  - verification: PowerShell AST parse (3/3 passed), preflight (passed; port conflict detected), database health verified, backend/frontend identities verified, wrong service rejected on port 3000, health API test passed (2/2), frontend lint (0 errors, 0 warnings), frontend build (13/13 routes), task validation (VALID);
  - next step: submit local commit to ChatGPT reviewer for review; do not push or merge

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

Only DLK-M3-031 is authorized for implementation.

After DLK-M3-031 is accepted, Member 3 feature work should stop unless a rehearsal or teammate integration run identifies a new reproducible blocker. Remaining work should be final team rehearsal, submission evidence/video, administrative upload, and merge/release coordination.
