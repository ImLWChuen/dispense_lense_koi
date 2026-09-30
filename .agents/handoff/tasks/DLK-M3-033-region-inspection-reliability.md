---
task_id: DLK-M3-033
title: Preserve region inspection reliability and prevent false missing deposits
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-032]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-033: Preserve region inspection reliability

## Objective

Establish trustworthy region-level inspection outcomes before overlays, template reuse, or automatic alignment. An unassessed region must never be reported as a missing deposit solely because its measured area is zero or its measurement is absent. Expose the reason through additive API fields while retaining conservative whole-image classification behavior in this first increment.

## Current evidence

- Planning baseline: local `backend-database` at `a4cb267`, synchronized with fetched main; DLK-M3-032 accepted at `01640a7fb3344d49a3dedc478d75ad3bc7f1d475`.
- `segment_roi` already returns status, quality, is_missing, and warnings. Its genuine empty-site path uses SUCCESS plus is_missing; an unreliable zero-area path is not proof of absence.
- `calculate_roi_features` drops segmentation status and warnings when constructing RoiMeasurement.
- `calculate_aggregate_measurements` currently treats zero-area and omitted measurements as missing.
- Classifier gates image evidence on quality, and returns no observations when any region is unreliable. Preserve that conservative behavior here; partial evidence emission is deferred until consumers are designed for it.
- Read `docs/architecture/region-inspection-improvement-plan.md` as the broader draft roadmap. Repeated-layout versus varied-product scope remains undecided and does not block this task.
- Existing unrelated untracked `.agents.zip` and `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md` are acknowledged and excluded from staging. The draft roadmap is planner-authored and may be included with this task.

## Requirements

- Propagate explicit inspection status and region-specific warnings from segmentation into each ROI measurement.
- Add an inspection status with values `DETECTED`, `MISSING`, `UNASSESSED`. It describes observation reliability, not acceptance against product limits.
- A reliable successful segmentation with is_missing=true maps to MISSING; a reliable successful positive-area deposit maps to DETECTED. Failure, insufficient quality, or contradictory zero-area/no-missing results map to UNASSESSED.
- Use the existing reliability threshold consistently; do not tune thresholds or change diagnostic weights in this task.
- Preserve detailed warnings, including why a site is unassessed. Do not fabricate measurements or claim absence from camera failure, flat exposure, or an omitted result.
- Add aggregate `unassessed_roi_ids`; reserve `missing_roi_ids` for assessed missing sites. Expected IDs without measurements belong to unassessed, never missing. Keep lists disjoint and unique.
- Mean coverage and size CV must exclude missing and unassessed regions. Zero eligible measurements produces null statistics; fewer than two eligible deposits produces null size CV.
- Any UNASSESSED current or reference region must prevent score-bearing observations in calibrated modes for this increment, even if its numeric quality happens to be high. FEATURES_ONLY remains neutral and UNCALIBRATED.
- Keep existing successful normal, missing, spread, and shape behavior. Do not treat DETECTED as a pass against process limits.

## Interfaces and data contracts

Authorized additive changes: RoiMeasurement gains `inspection_status` and `inspection_warnings`; AggregateMeasurements gains `unassessed_roi_ids`. Preserve existing keys, endpoint, request profile, units, and global AnalysisStatus values.

Use safe defaults for existing serialized measurements that lack new fields: status defaults to UNASSESSED and warnings to an empty list. All new measurements produced by the pipeline must explicitly set status. Update synthetic test constructors to explicitly represent their intended assessed state rather than weakening reliability checks. Historical data must remain parseable without being silently promoted to reliable evidence.

Map internal segmentation statuses without importing service-layer enums into schemas in a way that creates circular dependencies. Both current and reference images must use the same mapping. Preserve is_missing for compatibility but it must be false for UNASSESSED outputs. Top-level warnings must expose affected IDs/reasons to existing clients that ignore additive fields.

No database migration or historical record rewrite. Document additive fields and conservative image-level gating in the existing API specification. Partial classification, masks/contours, and new global states are future work.

## Allowed paths

- `backend/app/schemas/image.py`
- `backend/app/api/images.py`
- `backend/app/services/vision/measurement.py`
- `backend/app/services/vision/defect_classifier.py`
- `backend/tests/unit/test_vision_*.py`
- `backend/tests/integration/test_image*.py`
- `backend/tests/fixtures/synthetic_images.py`
- `docs/api/api-spec.md`
- `docs/architecture/region-inspection-improvement-plan.md` (include existing draft; record this increment only)
- `.agents/handoff/tasks/DLK-M3-033-region-inspection-reliability.md`
- `.agents/handoff/QUEUE.md`

## Prohibited scope

Frontend changes, automatic site detection, templates, alignment, segmentation algorithm replacement, new models/dependencies, threshold tuning, bubble-rule changes, cause scores, partial score-bearing evidence, database schemas, production data modification, remote Git operations, and changes to main.

## Implementation guidance

1. Read repository instructions, PROJECT.md, QUEUE.md, prerequisite review, and applicable source/tests. Verify branch and preserve unrelated work.
2. Add failing regressions for unreliable zero-area results and expected IDs without measurements being mislabeled missing. Record the intended failure before implementing.
3. Add fields and propagation, then update aggregate selection and explicit-status classification gates. Preserve calibrated missing detection only when missing is actually established.
4. Test both numeric-quality and status gates independently, including high-quality UNASSESSED input. Preserve per-region warnings in the response and expose unassessed IDs at image level.
5. Use synthetic fixtures for deterministic behavior; at least one API regression must exercise real segmentation on a uniform/uninspectable image. Mocks may supplement status combinations but must not replace that end-to-end path.
6. Inspect consumers read-only for compatibility. If a required fix lies outside allowed paths, report the specific dependency before expanding scope.
7. Update API documentation and implementation report. Mark implemented only after required verification succeeds.

## Acceptance criteria

- [x] Uniform/uninspectable image returns UNASSESSED region(s), no missing IDs, meaningful warnings, and no diagnostic observations.
- [x] A reliable empty expected site remains MISSING, and its presence evidence still respects the configured mode and limits.
- [x] An expected ROI with no measurement is unassessed, not missing.
- [x] A mixed valid/unassessed image preserves valid region measurements, excludes unassessed values from aggregates, and conservatively emits no diagnostic observations.
- [x] All-unassessed and fewer-than-two-valid-deposit aggregate boundaries behave as specified.
- [x] Explicit UNASSESSED overrides a misleading high numeric quality value for both current and reference classification.
- [x] FEATURES_ONLY remains neutral; existing image validation/upload limits remain enforced.
- [x] Legacy measurements parse with safe defaults; new responses carry status and warnings without removing existing fields.
- [x] API regression coverage uses at least one real synthetic image pipeline; existing suites pass without disabling safety checks or weakening unrelated assertions.
- [x] No unrelated files changed or staged; report makes no real-world accuracy claims.

## Verification

From repository root, run these PowerShell single-line commands:

1. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_segmentation.py backend/tests/unit/test_vision_measurement.py backend/tests/unit/test_vision_defect_classifier.py backend/tests/integration/test_image_api.py backend/tests/integration/test_image_diagnosis_integration.py backend/tests/integration/test_image_driven_case_workflow.py -q --basetemp=backend/.task033-focused -p no:cacheprovider`
2. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task033-full -p no:cacheprovider`
3. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-033-region-inspection-reliability.md`
4. `git diff --check`

Database-backed tests must use the configured safe disposable TEST_DATABASE_URL and existing safety bootstrap. Preserve development records; do not bypass safeguards or print secrets. If required infrastructure is unavailable, record the exact blocker rather than reporting success. Frontend lint/build are not required because frontend code is excluded.

## Planner decision boundaries

The additive fields and conservative status gating above are authorized within Member 3 scope. Return before introducing new global statuses, partial evidence semantics, schema migrations, frontend changes, dependencies, changed knowledge/scoring, or other expanded scope. Routine naming and private helper choices are implementer decisions.

## Git instructions

Create one atomic local commit after checks pass. Include this packet, queue, API docs, existing planner roadmap, and scoped implementation/tests. Do not stage unrelated files. Do not push, merge, rebase, create a PR, or change main. Do not alter prior accepted review records.

Proposed commit message: `fix(vision): distinguish unassessed regions from missing deposits`

## Implementation report

### Summary

- Implemented `RoiInspectionStatus` enum (`DETECTED`, `MISSING`, `UNASSESSED`) and added additive fields `inspection_status` and `inspection_warnings` to `RoiMeasurement`, and `unassessed_roi_ids` to `AggregateMeasurements`.
- Updated `calculate_roi_features` to map reliable segmentations with `is_missing=True` to `MISSING`, reliable positive-area segmentations to `DETECTED`, and unreliable, low-quality (<0.4), failed, or contradictory zero-area segmentations to `UNASSESSED`. Set `is_missing=False` for all unassessed regions to strictly prevent false missing deposit reports.
- Updated `calculate_aggregate_measurements` to separate confirmed `missing_roi_ids` from `unassessed_roi_ids`, ensure both lists are strictly disjoint, and compute `mean_coverage` and `size_cv` strictly over eligible `DETECTED` deposits with positive area (null statistics for 0 eligible; null size CV for <2 eligible). Expected ROIs lacking measurement data are mapped to `unassessed_roi_ids`, never `missing_roi_ids`.
- Enforced conservative whole-image classification gating in `classify_defects_from_measurements`: any unassessed current or reference region forces `AnalysisStatus.UNRELIABLE`, zero score-bearing observations (`observations = []`), and surfaces affected ROI IDs and reasons in top-level `warnings`. Explicit `UNASSESSED` status strictly overrides artificial or misleading high numeric quality scores.
- Resolved review finding R1: in `classify_defects_from_measurements`, collect and deduplicate all applicable current and reference reliability explanations into top-level warnings before any mode or status early returns. Moved expected-but-omitted ROI warning collection outside nonempty measurement branches for both current and reference images, safely handling empty or None lists. Preserved `FEATURES_ONLY` as `UNCALIBRATED` with no observations, carrying top-level failure explanations; preserved calibrated-mode `UNRELIABLE` gating with empty observations in `PROCESS_LIMITS` and `REFERENCE_IMAGE`.
- Documented additive fields, status semantics, aggregate boundaries, and conservative whole-image gating in `docs/api/api-spec.md`, and noted Phase 1 progress in `docs/architecture/region-inspection-improvement-plan.md`.

### Files changed

- `backend/app/schemas/image.py`: added `RoiInspectionStatus` enum; added `inspection_status` and `inspection_warnings` to `RoiMeasurement`; added `unassessed_roi_ids` to `AggregateMeasurements`.
- `backend/app/services/vision/measurement.py`: implemented reliable status mapping and warnings preservation in `calculate_roi_features`; updated aggregate calculations for disjoint `missing_roi_ids` and `unassessed_roi_ids`, and boundary metrics.
- `backend/app/services/vision/defect_classifier.py`: enforced conservative gating on `UNASSESSED` current and reference ROIs; resolved R1 by collecting all current and reference reliability explanations before early returns across all analysis modes, including expected-but-omitted ROIs outside nonempty branches with empty/None safety.
- `backend/tests/unit/test_vision_measurement.py`: added regression tests for unreliable zero-area and omitted ROIs, aggregate boundary tests, and legacy serialized payload defaults tests.
- `backend/tests/unit/test_vision_defect_classifier.py`: added tests verifying explicit `UNASSESSED` status overrides quality 1.0; added R1 regressions for multiple unassessed reference regions, simultaneous current/reference failures, and empty current/reference measurement lists with populated unassessed IDs.
- `backend/tests/integration/test_image_api.py`: added end-to-end integration tests for uniform uninspectable image, defensible missing deposit, mixed valid/unassessed ROIs, and R1 regression for real uniform `FEATURES_ONLY` image exposing top-level warnings.
- `docs/api/api-spec.md`: documented additive fields, status semantics, aggregate boundaries, and conservative whole-image classification gating.
- `docs/architecture/region-inspection-improvement-plan.md`: recorded Phase 1 progress for increment DLK-M3-033.
- `.agents/handoff/QUEUE.md`: updated DLK-M3-033 status to `implemented` with R1 resolution details.
- `.agents/handoff/tasks/DLK-M3-033-region-inspection-reliability.md`: updated status to `implemented` and completed implementation report with R1 review resolution.

### Decisions made

- `is_missing` compatibility: strictly set to `False` for `UNASSESSED` outputs; only `True` when `inspection_status == RoiInspectionStatus.MISSING` to prevent downstream consumers from treating unassessed sites as absent deposits.
- Unassessed warning propagation: detailed per-region warnings from segmentation are preserved on `RoiMeasurement.inspection_warnings`, and top-level `ImageAnalysisResponse.warnings` lists affected unassessed ROI IDs and reasons for clients ignoring additive fields before any early returns.
- Strict conservative whole-image gating: in calibrated modes (`PROCESS_LIMITS` and `REFERENCE_IMAGE`), any unassessed region returns `UNRELIABLE` with no diagnostic observations, deferring partial-evidence emission until consumers are designed for it.
- Safe defaults: historical serialized data without new fields defaults to `UNASSESSED`, `[]`, and `[]`, ensuring backwards compatibility without promoting legacy unvalidated data to reliable evidence.

### Verification results

- Failing regression recorded before implementation:
  - `test_regression_unreliable_zero_area_not_mislabeled_as_missing`: `AssertionError: assert 'roi_bad' not in ['roi_bad']`
  - `test_regression_omitted_roi_not_mislabeled_as_missing`: `AssertionError: assert 'roi_omitted' not in ['roi_omitted']`
- Post-implementation verification commands:
  - Focused test suite: `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_segmentation.py backend/tests/unit/test_vision_measurement.py backend/tests/unit/test_vision_defect_classifier.py backend/tests/integration/test_image_api.py backend/tests/integration/test_image_diagnosis_integration.py backend/tests/integration/test_image_driven_case_workflow.py -q --basetemp=backend/.task033-focused -p no:cacheprovider` -> `66 passed, 20 warnings in 2.36s`
  - Full test suite: `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task033-full -p no:cacheprovider` -> `529 passed, 42 warnings in 59.49s`
  - Task packet validation: `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-033-region-inspection-reliability.md` -> `VALID: .agents\handoff\tasks\DLK-M3-033-region-inspection-reliability.md`
  - Git whitespace diff check: `git diff --check` -> clean (exit code 0)

### Limitations and follow-up

- Partial analysis (score-bearing observations for subset of valid ROIs when one ROI is unassessed) is intentionally deferred; currently returns conservative `AnalysisStatus.UNRELIABLE`.
- Visual overlays, bounded contour/mask coordinates, template storage, and automatic site alignment/detection remain deferred to subsequent phases as planned in `docs/architecture/region-inspection-improvement-plan.md`.

### Proposed commit message

`fix(vision): collect omitted ROI warnings for empty current and reference lists (R1)`
