---
task_id: DLK-M3-042
title: Verify the integrated region inspection workflow and record readiness
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-041]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-042: Integrated region inspection acceptance

## Objective

Establish a repeatable acceptance checkpoint for the currently implemented manual-ROI workflow: image analysis, technician inspection, durable case evidence, and JSON/PDF export. Produce reproducible integration tests and a concise synthetic rehearsal/readiness record. This task verifies the delivered slice before profiles/alignment or partial-evidence behavior is planned; it does not authorize those features or claim production accuracy.

## Current evidence

- DLK-M3-041 is accepted at `938e99de0825167b7dadc5a72bbce2d684e93448`, with implementation at `5af203c`. Its accepted review and queue edits are pending planner artifacts.
- DLK-M3-033–037 deliver reliability, outlines, affected-site provenance, and separate current/reference coverage. DLK-M3-038 provides a six-case/nine-site synthetic baseline. DLK-M3-039–040 persist site measurements/limits and expose them in JSON/PDF reports. DLK-M3-041 adds the upload/studio workbench.
- Existing tests cover many individual boundaries, but no one acceptance scenario exercises the public multipart endpoint through durable multi-site evidence, a later revision, and both report formats with the current contract.
- `test_image_driven_case_workflow.py` calls _sync_analyze_image directly; `test_mvp_backend_acceptance.py` supplies established lifecycle requests and read-only assertions. Reuse existing test/database safety infrastructure.
- `frontend/components/diagnosis/ImageAnalysis.tsx` on the saved diagnosis page still reads legacy first-site metadata rather than region_evidence. Record this known presentation limitation; do not silently equate upload workbench completion with complete saved-case UX integration.
- Mixed/unassessed calibrated images still emit no diagnostic observations. Per-region display is available, but partial score-bearing evidence is deliberately deferred. No original image storage or saved-image reconstruction exists under this scope.

## Requirements

- Add a focused integration acceptance module using the actual multipart POST /api/v1/images/analyze endpoint and public durable case/report APIs. Use deterministic in-memory synthetic images, explicit ROIs and supplied limits; no network/LLM calls, real user images, or persisted image files.
- Scenario A: two distinct detected sites producing one deduplicated undersized observation. Verify ordered affected IDs, each site's different measurement snapshot, supplied limits, and source. Create a synthetic durable case from the response, retrieve it, submit a valid existing check to advance revision, and verify unchanged metadata in the later case and JSON report. Parse the PDF with existing pypdf and verify both site IDs and distinguishable displayed measurements on the correct report revision. Do not hardcode nondeterministic UUIDs/timestamps or invent a success outcome.
- Scenario B: mixed detected/unassessed input. Verify PARTIAL coverage with explicit counts, per-site statuses/warnings, top-level UNRELIABLE, and zero emitted observations. Do not fabricate an image-derived case finding when the gate returns none.
- Scenario C: confirmed missing expected site with adequate existing synthetic fiducial context. Verify MISSING differs from UNASSESSED and emitted missing evidence is controlled by explicit limits. If the existing fixture cannot establish that condition, report the mismatch rather than changing labels or tuning classification.
- Scenario D: reference mode with current/reference coverage kept separate, including an unassessed reference that prevents score-bearing comparison. Keep existing conservative reference behavior; no alignment assumption.
- Prefer a small number of meaningful cross-boundary scenarios over duplicating every existing unit test. Preserve safe test-database destination checks and isolate/clean up only cases created by these tests. Never remove development records or volumes.
- Add a short repeatable synthetic rehearsal guide and readiness matrix under docs/demo/region-inspection-acceptance.md. State prerequisites, precise sample/profile generation or reuse steps, input labels, user actions, expected visible outputs, and known limitations. Use [SYNTHETIC DEMO] for user-entered rehearsal text.
- Perform one real browser walkthrough on port 3001 using actual backend responses through image upload/Analyze, region selection, Start Diagnosis, saved-case reload, and PDF download. Reuse the existing demo runbook and safe environment configuration; prefer an isolated disposable test database for writes. Record environment identity and synthetic case ID without credentials. Do not reset or alter an existing service's database implicitly.
- Inspect the resulting PDF visually with available tooling if possible; record unavailable tools as a limitation, never conflate text extraction with visual inspection. Browser walkthrough itself is required. Clearly distinguish mocked-state checks from real end-to-end execution.
- Record findings honestly: the known saved-case first-site display and conservative partial-evidence gate are deferred limitations, not newly failing acceptance assertions. Any new contradiction/data-loss/crash is a blocker to readiness and must be reported to the planner, not fixed by expanding this task.
- Update roadmap progress to distinguish accepted increments from incomplete phase-level acceptance. Do not mark Phase 1 complete while partial evidence is deferred, Phase 3 complete without profiles/alignment, or Phase 5 complete without representative data and evaluation decisions.

## Interfaces and data contracts

No public API, frontend, storage, or diagnostic contract changes. Tests consume current ImageAnalysisResponse, CaseObservationResponse.metadata, CaseReportResponse.image_observations, and the standard report.pdf endpoint. Evidence remains diagnostic support, not root-cause confirmation or process acceptance. Browser checks must not imply missing observations mean all expected sites passed.

## Allowed paths

- `backend/tests/integration/test_region_inspection_acceptance.py` (new)
- `docs/demo/region-inspection-acceptance.md` (new)
- `docs/architecture/region-inspection-improvement-plan.md` (progress/readiness wording only)
- `.agents/handoff/tasks/DLK-M3-042-region-inspection-acceptance.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-041-review.md` (include accepted planner record unchanged)

## Prohibited scope

Production code changes, new dependencies/frameworks, segmentation tuning, changing existing labels/tests to force success, frontend redesign, shared database mutations/cleanup, image retention, templates/alignment, partial evidence, score changes, remote Git operations, or main changes. Preserve unrelated .agents.zip and .agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md. Do not commit screenshots/PDFs or secret-bearing logs; keep reviewable textual evidence with local artifact locations where available.

## Implementation guidance

1. Read applicable instructions, PROJECT.md, QUEUE.md, accepted prerequisite review, roadmap, existing image/lifecycle/report tests, synthetic fixture helpers and demo runbook.
2. Build the smallest integration module around existing fixtures and disposable database bootstrap. Exercise real route handlers; do not mock vision/classification/storage merely to meet expected results.
3. Run focused checks, inspect actual response values, and write the rehearsal guide from current rendered controls. Document the supported scope and unresolved decisions.
4. Perform and record the real browser workflow; inspect saved evidence and downloaded report. Record known UI limitations explicitly. Stop feature changes and report unexpected failures for planner review.
5. Run required verification, complete the report and queue, and commit scoped files locally. If checks are blocked, record the exact cause and mark blocked; do not claim ready-for-demo based solely on prior task results.

## Acceptance criteria

- [x] Public-API integration proves distinct multi-site evidence survives case creation, a later revision, JSON export and PDF content without duplication or loss.
- [x] Mixed-quality, missing-site, and unreliable-reference scenarios preserve existing status/coverage/gating semantics.
- [x] Tests use only disposable data and preserve development records; no production behavior changes.
- [x] Repeatable rehearsal instructions match the current UI and distinguish actual backend execution from mocked scenarios.
- [x] Real browser walkthrough is recorded with observed results, environment/commit identity and known saved-case presentation limits.
- [x] Readiness matrix separates scoped manual workflow readiness from full-roadmap completion and real-image accuracy; no unsupported pass/accuracy claim.
- [x] Required automated checks pass against final test changes, and only scoped files are committed locally.

## Verification

From repository root in PowerShell, using the existing safe disposable TEST_DATABASE_URL configuration without printing credentials:

1. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_region_inspection_acceptance.py -q --basetemp=backend/.task042-focused -p no:cacheprovider`
2. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task042-full -p no:cacheprovider`
3. `& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_baseline.py` (record actual baseline; timing is descriptive, not a quality target)
4. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-042-region-inspection-acceptance.md`
5. `git diff --check`

Browser execution follows the current startup runbook and the acceptance scenarios above. No frontend rebuild is required solely for new backend tests/docs; carry forward the previously accepted frontend check provenance unless frontend code changes unexpectedly. A production change outside this allowlist requires a planner decision.

## Planner decision boundaries

This acceptance/rehearsal task is authorized. Return to the planner before production fixes, broader frontend ownership, new dependencies, database/schema changes, new data retention, segmentation tuning, or adopting numerical accuracy targets. Template scope/storage, partial evidence semantics, and access to representative labeled images remain team decisions.

## Git instructions

Use backend-database. Include the completed task, queue and pending accepted DLK-M3-041 review unchanged in one local commit. Do not push, merge, rebase, create a PR, or change main.

Proposed commit message: `test(vision): verify integrated region inspection workflow`

## Implementation report

### Summary

- Implemented an integration acceptance test module (`backend/tests/integration/test_region_inspection_acceptance.py`) covering Scenarios A–D:
  - **Scenario A:** Multipart `POST /api/v1/images/analyze` with two distinct detected sites producing one deduplicated undersized observation. Verified ordered affected IDs, distinct site snapshots, and applied limits. Created durable case, advanced revision to Revision 2 via check submission (`ACT01`), verified unchanged metadata in later case and JSON report, and parsed the Revision 2 PDF report with `pypdf`, verifying both site IDs and distinguishable measurements.
  - **Scenario B:** Mixed detected/unassessed input verifying `PARTIAL` coverage with explicit counts (`expected_roi_count=2, assessed_roi_count=1`), per-site statuses (`DETECTED` vs `UNASSESSED`) and inspection warnings, top-level `UNRELIABLE`, and zero emitted observations.
  - **Scenario C:** Confirmed missing expected site with synthetic fiducial context verifying `MISSING` differs from `UNASSESSED` (assessed outcome, `COMPLETE` coverage), and emitted missing evidence is controlled by explicit limits (emitted on `min_presence_ratio`, suppressed on `max_size_cv`).
  - **Scenario D:** Reference mode with current/reference coverage kept separate, including unassessed reference reporting `UNRELIABLE` with zero score-bearing observations while preserving `COMPLETE` current coverage and separate `NONE` reference coverage.
- Created `docs/demo/region-inspection-acceptance.md` containing a repeatable competition demonstration guide using rendered UI controls and `[SYNTHETIC DEMO]` prefixes, a scoped readiness matrix separating manual workflow readiness from deferred roadmap features, and documented operational limitations.
- Executed and recorded a real browser walkthrough on port 3001 with running backend on port 8000 using Chrome DevTools Protocol (CDP) through image upload/Analyze, region inspection workbench display, case creation via Start Diagnosis, saved case reload (`case_id: ee5d0200-270c-4fbe-b1e8-5b5182af089a`), and PDF report download.
- Recorded observed findings and known presentation limitations (such as `ImageAnalysis.tsx` on the saved case page rendering legacy first-site metadata) without modifying production code.
- Updated progress checkpoint wording in `docs/architecture/region-inspection-improvement-plan.md`.

### Files changed

- `backend/tests/integration/test_region_inspection_acceptance.py` (new) — Integration acceptance tests for Scenarios A–D.
- `docs/demo/region-inspection-acceptance.md` (new) — Rehearsal guide, scoped readiness matrix, and limitation notes.
- `docs/architecture/region-inspection-improvement-plan.md` — Progress checkpoint wording updated for DLK-M3-042.
- `.agents/handoff/tasks/DLK-M3-042-region-inspection-acceptance.md` — Task packet updated to `implemented` with implementation report.
- `.agents/handoff/QUEUE.md` — Queue state updated to `implemented`.
- `.agents/handoff/reviews/DLK-M3-041-review.md` — Accepted review record included unchanged.

### Decisions made

- Isolated all automated integration tests to disposable `TEST_DATABASE_URL` (`dispenselens_test`) with automatic teardown in `cleanup_cases` fixture, preserving development records.
- Stored browser rehearsal scratch scripts, synthetic images, and screenshots outside the repository under the agent scratch directory (`C:\Users\Kee Chun Shang\.gemini\antigravity\brain\370fd0d2-fa15-4789-8553-059d74d93e3d\scratch\`), keeping the working tree clean of binary artifacts.
- Maintained existing conservative quality gates (zero score-bearing observations emitted on unassessed regions or unassessed reference) without attempting unauthorized partial evidence scoring.
- Kept the known saved-case first-site display limitation documented rather than expanding into frontend refactoring.
- Recorded that visual PDF rasterizer tools (`pdftoppm`, `mutool`) are unavailable on the Windows host as an explicit tooling limitation while verifying parsed PDF text and structure with `pypdf`.

### Verification results

1. **Focused Acceptance Tests (`pytest backend/tests/integration/test_region_inspection_acceptance.py`):**
   - Output: `4 passed, 11 warnings in 4.19s` against disposable test database.
2. **Full Backend Test Suite (`pytest backend/tests`):**
   - Output: `605 passed, 42 warnings in 64.11s` against disposable test database.
3. **Synthetic Vision Inspection Baseline (`python backend/tests/vision_inspection_baseline.py`):**
   - Output: `6 cases, 9 expected sites, status_accuracy=1.0, outline_availability_rate=1.0, mean_outline_iou=0.997 in 0.0214s`.
4. **Real End-to-End Browser Rehearsal Walkthrough (CDP on port 3001 & 8000):**
   - Executed against live running services on `http://localhost:3001` and `http://127.0.0.1:8000`:
     - Navigated to `/diagnosis/new`.
     - Filled Problem Form with `[SYNTHETIC DEMO]` description, material, line, and defect `D01_TOO_LITTLE`.
     - Uploaded synthetic multi-site test image (`acceptance_sample.png`).
     - Observed workbench rendering `CALIBRATED` status, deposit outlines (`hasPolygons: 1`), and target site tabs.
     - Clicked `Start Diagnosis`; case created via backend `POST /api/v1/cases`; navigated to `/diagnosis/ee5d0200-270c-4fbe-b1e8-5b5182af089a`.
     - Loaded saved case at Revision 1 with ranked candidate causes (`Nozzle Restriction` at 62.0).
     - Inspected `/diagnosis/ee5d0200-270c-4fbe-b1e8-5b5182af089a/analysis`; verified `ImageAnalysis` component rendered persisted observations and confirmed known limitation (first-site metadata display).
     - Downloaded PDF report: `GET /api/v1/cases/ee5d0200-270c-4fbe-b1e8-5b5182af089a/report.pdf` (10,657 bytes, starts with `%PDF`, Section 8 Image Inspection Evidence verified with `pypdf`).
     - Checked rasterizer tools: `pdftoppm=false, mutool=false` (recorded as tooling limitation).
5. **Frontend Provenance:**
   - Carried forward from accepted DLK-M3-041 commit `938e99d` (0 errors, 140 warnings lint; 20/20 routes compiled cleanly; zero frontend code changes).
6. **Task Validation (`validate_task.py`):**
   - Result: `VALID: .agents\handoff\tasks\DLK-M3-042-region-inspection-acceptance.md`.
7. **Whitespace Check (`git diff --check`):**
   - Output: clean, zero whitespace errors.

### Limitations and follow-up

- **Manual-ROI Workflow Readiness:** Fully verified across API, durable PostgreSQL persistence, check execution revision progression, JSON/PDF export, and frontend upload workbench.
- **Saved-Case Frontend Display:** `ImageAnalysis.tsx` on the saved case page renders legacy first-site metadata; multi-site tabbed presentation on saved cases is deferred to Phase 4.
- **Partial Evidence Gating:** Partially unassessed calibrated images emit zero score-bearing observations by design.
- **Reusable Profiles & Auto-Alignment:** Deferred to Phase 3.
- **Industrial Manufacturing Accuracy:** Unmeasured on real-world factory camera images; production accuracy claims require held-out datasets and team accuracy metrics.

### Proposed commit message

`test(vision): verify integrated region inspection workflow`
