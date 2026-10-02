---
task_id: DLK-M3-036
title: Expose truthful expected-site inspection coverage
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-035]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-036: Expected-site inspection coverage

## Objective

Return a small, explicit coverage summary for the **current image** so a later technician-facing workbench can distinguish complete, partial, and absent inspection of configured dispensing sites. This is the next backend foundation for partial-region handling; this task must not turn findings from a partially inspected image into diagnosis evidence.

## Current evidence

- DLK-M3-035 is accepted at `2977003e72b8a8fd9a3697a95c543f3ce5465b31`; its accepted review and queue changes are uncommitted planner handoff records to include in this task's local commit.
- `calculate_aggregate_measurements` in `backend/app/services/vision/measurement.py` receives both `roi_measurements` and expected `all_roi_ids`. It already distinguishes confirmed missing sites from unassessed sites (including omitted measurements) and excludes unassessed sites from mean coverage and size CV. The response does not explicitly report expected/assessed counts or whether inspection coverage is complete.
- `AggregateMeasurements` in `backend/app/schemas/image.py` is returned in `ImageAnalysisResponse`. The current status enum (`CALIBRATED`, `UNCALIBRATED`, `UNRELIABLE`) describes analysis reliability, not site coverage. `frontend/app/(dashboard)/diagnosis/new/page.tsx` and `frontend/components/diagnosis/ImageUpload.tsx` consume score-bearing image observations only when analysis status is `CALIBRATED`.
- In calibrated modes, any unassessed site currently forces `UNRELIABLE` and zero observations. Preserve that gate in this task. `FEATURES_ONLY` remains neutral. Reference-image measurements are calculated internally, but the response exposes only the current-image aggregate; do not imply this new coverage summary describes the reference image.
- `docs/architecture/region-inspection-improvement-plan.md` calls for an assessed numerator and expected denominator before partial-evidence semantics. Synthetic fixtures can verify software behavior but cannot establish industrial inspection accuracy.
- Preserve unrelated untracked `.agents.zip` and `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md`; do not stage them.

## Requirements

- Add an **additive**, typed current-image inspection summary to `AggregateMeasurements`: `expected_roi_count`, `assessed_roi_count`, and `inspection_coverage_status` with `COMPLETE`, `PARTIAL`, and `NONE` values. Use nullable defaults for newly deserialized legacy aggregates so absent historical fields mean **unknown**, not a fabricated zero-site inspection. Newly calculated aggregates always populate all three fields.
- Count unique expected ROI IDs supplied in `all_roi_ids`; count an expected site as assessed only when its measurement has explicit `DETECTED` or confirmed `MISSING` inspection status. An `UNASSESSED` status or omitted expected measurement is not assessed. A confirmed missing deposit **is** an assessed site; it is not the same as an unassessed site. Ignore unexpected measurement IDs for the numerator and denominator. Avoid duplicate counts if an internal caller supplies a repeated expected ID.
- Derive `NONE` when no expected site is assessed, `COMPLETE` when every expected site is assessed and the expected count is positive, and `PARTIAL` otherwise. For the internal empty-expected-list edge case, report `0/0` and `NONE`, never `COMPLETE`.
- Keep `missing_roi_ids`, `unassessed_roi_ids`, existing metrics, their warnings, and ordering correct and consistent with the summary. Do not count a site as assessed merely because it has numeric measurement fields. Do not make an all-clear or pass/fail claim from this coverage summary.
- Preserve the current classifier, analysis status, observation set, evidence score, image/case persistence, frontend behavior, and reference-mode safety gate exactly. In particular, mixed reliable/unassessed input remains `UNRELIABLE` with zero score-bearing observations; this task exposes scope, not partial evidence.
- Document each new field, its current-image-only scope, how missing and unassessed sites affect counts, and the difference between inspection coverage and deposit-area `coverage_ratio` / diagnostic Evidence Support /100.

## Interfaces and data contracts

- Authorized additive fields on existing `AggregateMeasurements` response: `expected_roi_count: int | null`, `assessed_roi_count: int | null`, and `inspection_coverage_status: InspectionCoverageStatus | null` (`COMPLETE | PARTIAL | NONE`). No new endpoint, request field, database column, or top-level analysis-status value.
- Newly calculated responses from `POST /api/v1/images/analyze` must have non-null counts/status. Null defaults are for parsing older stored/serialized aggregate data, and mean unknown coverage. Do not synthesize counts from historical numeric metrics when the expected site set is unavailable.
- The summary describes the uploaded **current image** even in `REFERENCE_IMAGE` mode. It does not certify reference-image reliability, material volume, root cause, or acceptance against limits. Top-level warnings and analysis status retain their existing roles.
- Member 1 owns UI rendering and frontend type changes; Member 2 owns diagnostic scoring and interpretation. This task authorizes the additive backend response contract and documentation only. Return to the planner if implementation requires either owner's code or a changed status/scoring meaning.

## Allowed paths

- `backend/app/schemas/image.py`
- `backend/app/services/vision/measurement.py`
- `backend/tests/unit/test_vision_measurement.py`
- `backend/tests/integration/test_image_api.py`
- `docs/api/api-spec.md`
- `docs/architecture/region-inspection-improvement-plan.md` for a brief task-status note
- `.agents/handoff/tasks/DLK-M3-036-inspection-coverage-summary.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-035-review.md` (include the planner-authored acceptance record unchanged)

## Prohibited scope

Changing `defect_classifier.py`, diagnosis rules or weights, frontend files, report or AI prompt projection, database models or migrations, partial score-bearing evidence, segmentation thresholds, reference registration, reusable templates, new dependencies, remote Git operations, or the base branch.

## Implementation guidance

1. Confirm branch and Git state, read repository instructions and the accepted DLK-M3-035 review, and preserve unrelated files. Inspect current aggregate and API tests before editing.
2. Add focused failing tests for fully assessed detected/missing sites; detected plus unassessed; all unassessed; omitted expected measurement; duplicate expected IDs; unexpected measurement IDs; and legacy deserialization without the new fields. Then implement the smallest compatible aggregate/schema change.
3. Extend the existing real synthetic mixed-image API test to assert the populated `1/2 PARTIAL` summary while its `UNRELIABLE`/empty-observations safety gate remains. Cover a complete image and an all-unassessed image through the API as well. Do not infer that `PARTIAL` means a defect or that `COMPLETE` means all deposits passed limits.
4. Update the API spec and one roadmap status note. Complete this packet's implementation report, verify the final diff, and include the pending DLK-M3-035 acceptance records in one scoped local commit.

## Acceptance criteria

- [x] A complete current-image inspection reports the expected denominator and matching assessed numerator, including confirmed missing sites, with `inspection_coverage_status=COMPLETE`.
- [x] Mixed detected/missing and unassessed or omitted expected sites report the exact numerator/denominator and `PARTIAL`; no assessed site is misclassified as unassessed or vice versa.
- [x] No assessed expected sites, including the zero-expected internal edge case, report `NONE`; repeated expected IDs and unexpected measurement IDs do not distort counts.
- [x] Legacy aggregates missing the additive fields parse with `null`/unknown defaults; new API responses provide non-null, JSON-compatible fields.
- [x] Existing `mean_coverage`, `size_cv`, missing/unassessed lists, warning behavior, calibrated-mode conservative gate, FEATURES_ONLY neutrality, observation counts, and diagnostic evidence semantics remain unchanged.
- [x] The API spec distinguishes inspection coverage from deposit coverage and evidence score, and states that reference-image coverage is not represented by this current-image aggregate.
- [x] Only scoped files are committed locally, after focused and full backend checks pass. No remote Git operation occurs.

## Verification

Run from repository root in PowerShell. For any database-backed tests in the full suite, use the existing safe disposable `TEST_DATABASE_URL` setup; never bypass its destination check or touch the development/demo database.

1. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_measurement.py backend/tests/integration/test_image_api.py -q --basetemp=backend/.task036-focused -p no:cacheprovider`
2. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task036-full -p no:cacheprovider`
3. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-036-inspection-coverage-summary.md`
4. `git diff --check` and inspect both staged and unstaged changes before committing.

If infrastructure or a required check is unavailable, record the exact blocker and report `blocked` rather than claiming completion. Frontend checks are not required because frontend files are excluded.

## Planner decision boundaries

The three additive aggregate fields and their semantics above are authorized. Return to the planner before changing the public request shape, top-level analysis status, observation eligibility, partial-evidence/scoring behavior, database storage, reference-result exposure, Member 1 frontend code, or Member 2 diagnostic logic. A later task must coordinate partial score-bearing evidence with the frontend's current `CALIBRATED` gate.

## Git instructions

Commit this ready task packet, implementation report, queue, pending DLK-M3-035 accepted review, and scoped code/tests/docs in one atomic local commit after checks pass. Do not stage unrelated files. Do not push, merge, rebase, create a PR, or change main.

Proposed commit message: `feat(vision): report expected-site inspection coverage`

## Implementation report

### Summary

Implemented an additive, typed current-image inspection coverage summary on `AggregateMeasurements`: `expected_roi_count: int | null`, `assessed_roi_count: int | null`, and `inspection_coverage_status: InspectionCoverageStatus | null` with `COMPLETE`, `PARTIAL`, and `NONE` values. In `calculate_aggregate_measurements`, unique expected ROI IDs from `all_roi_ids` form the denominator (`expected_roi_count`), while expected sites with explicit `DETECTED` or confirmed `MISSING` inspection status form the assessed numerator (`assessed_roi_count`). Confirmed missing deposits are treated as assessed sites, distinguishing them from unassessed sites. The summary reports `COMPLETE` when all expected sites are assessed (expected > 0), `PARTIAL` when at least one site is assessed but some are unassessed or omitted, and `NONE` when no expected sites are assessed (or for the 0/0 edge case). Legacy aggregates missing these fields safely deserialize with `null` defaults (representing unknown coverage). Conservative whole-image gating on unassessed regions in calibrated modes, diagnostic scoring, and reference image safety remain strictly preserved.

### Files changed

- `backend/app/schemas/image.py`: Defined `InspectionCoverageStatus` enum (`COMPLETE`, `PARTIAL`, `NONE`) and added `expected_roi_count`, `assessed_roi_count`, and `inspection_coverage_status` fields with `None` defaults to `AggregateMeasurements`.
- `backend/app/services/vision/measurement.py`: Implemented expected site deduplication, assessed site counting (`DETECTED` or `MISSING`), and coverage status derivation (`COMPLETE`, `PARTIAL`, `NONE`) in `calculate_aggregate_measurements`.
- `backend/tests/unit/test_vision_measurement.py`: Added 8 focused unit tests covering complete detected/missing, partial unassessed, all unassessed, omitted expected measurements, duplicate expected IDs, unexpected measurement IDs, empty expected list edge case, and legacy deserialization defaults.
- `backend/tests/integration/test_image_api.py`: Updated mixed image integration test to assert `1/2 PARTIAL` summary, and added integration tests for complete (detected and missing deposits) and all-unassessed (`NONE`) coverage through `POST /api/v1/images/analyze`.
- `docs/api/api-spec.md`: Documented additive aggregate fields, updated JSON example payload, and added dedicated subsection distinguishing inspection coverage from deposit coverage and diagnostic Evidence Support /100.
- `docs/architecture/region-inspection-improvement-plan.md`: Added Phase 1 progress note for increment DLK-M3-036.
- `.agents/handoff/tasks/DLK-M3-036-inspection-coverage-summary.md`: Updated status to implemented, completed implementation report, and checked acceptance criteria.
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-036 status to implemented.

### Decisions made

- **Assessed Site Definition:** An expected site is counted as assessed if and only if it is present in expected `all_roi_ids` and its measurement has `inspection_status` of `DETECTED` or `MISSING`. Confirmed missing deposits are assessed because the substrate background verified the deposit's absence, distinguishing them from unassessed regions (e.g. flat exposure or camera failure).
- **Deduplicated Expected Site Order:** Deduplicated `all_roi_ids` via `list(dict.fromkeys(all_roi_ids))` to preserve input order and prevent caller duplicates from inflating the denominator or numerator.
- **Unexpected IDs Ignored:** Measurements with `roi_id` not found in `all_roi_ids` are ignored when calculating both numerator and denominator.
- **Zero-Expected Edge Case:** When `expected_roi_count == 0`, `inspection_coverage_status` derives to `NONE` (reporting 0/0, never `COMPLETE`).
- **Conservative Gating Preserved:** In calibrated modes, any unassessed region forces `UNRELIABLE` with `observations = []`. Exposing `PARTIAL` coverage does not release partial score-bearing observations.

### Verification results

1. Focused test suite:
   `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_measurement.py backend/tests/integration/test_image_api.py -q --basetemp=backend/.task036-focused -p no:cacheprovider`
   Result: `45 passed, 20 warnings in 1.84s`
2. Full backend test suite:
   `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task036-full -p no:cacheprovider`
   Result: `565 passed, 42 warnings in 63.31s`
3. Task validation script:
   `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-036-inspection-coverage-summary.md`
   Result: Validated (0 errors).
4. Whitespace check:
   `git diff --check`
   Result: Clean (0 whitespace errors).

### Limitations and follow-up

- Frontend display of inspection coverage badges/summaries is owned by Member 1 and was not modified in this backend task.
- Coverage summary describes only the uploaded current image; reference image coverage is evaluated internally and not exposed in the response.
- Score-bearing partial-evidence classification remains deferred to future increments.

### Proposed commit message

`feat(vision): report expected-site inspection coverage`
