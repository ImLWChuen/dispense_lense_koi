---
task_id: DLK-M3-037
title: Expose reference-image inspection coverage separately
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-036]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-037: Reference-image inspection coverage

## Objective

In `REFERENCE_IMAGE` analysis, return the already calculated aggregate for the reference image separately from the current-image aggregate. A technician or later workbench must be able to see whether the reference sites were inspected, without mistaking current-image coverage for reference reliability. Keep all diagnostic gating and scoring unchanged.

## Current evidence

- DLK-M3-036 is accepted at `86ae4ffd764213503e9e2dac6dbbe0c72784525c`; its accepted review and queue update are uncommitted planner handoff records to include in this task's local commit.
- `backend/app/api/images.py` already computes `ref_measurements` and `ref_agg = calculate_aggregate_measurements(ref_measurements, all_roi_ids)` in `REFERENCE_IMAGE` mode. It passes both into `classify_defects_from_measurements`, then returns only `aggregate_measurements=agg` for the current image.
- `AggregateMeasurements` already includes expected/assessed counts and `inspection_coverage_status` from DLK-M3-036. `ImageAnalysisResponse` has no reference aggregate field. The API spec explicitly states that the existing aggregate covers only the current image.
- The classifier treats an unassessed or missing reference region as unreliable for comparison. A reference site may have `inspection_coverage_status=COMPLETE` because `MISSING` is a reliably inspected state while the top-level analysis is still `UNRELIABLE` because a missing reference deposit cannot support comparison. Do not conflate these meanings.
- Member 1 owns frontend display/types and Member 2 owns diagnostic interpretation. This task changes only the additive backend response contract and its documentation; no UI or causal scoring changes are authorized.
- Preserve unrelated untracked `.agents.zip` and `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md`; do not stage them.

## Requirements

- Add `reference_aggregate_measurements: AggregateMeasurements | None = None` to `ImageAnalysisResponse`. In `REFERENCE_IMAGE` mode with a valid uploaded reference, populate it from the existing `ref_agg`. In `FEATURES_ONLY` and `PROCESS_LIMITS`, return `null` explicitly through normal serialization.
- Preserve `aggregate_measurements` as the current-image aggregate. Do not swap, merge, or overwrite its counts, warnings, missing/unassessed IDs, `mean_coverage`, or `size_cv` with reference data. The new reference aggregate must independently describe the same configured expected IDs on the reference image.
- In reference mode, return the reference aggregate even when reference inspection is partial or absent and top-level status is `UNRELIABLE`. Its coverage summary is information about inspection completeness, not permission to emit observations.
- Distinguish a confirmed `MISSING` reference deposit from an `UNASSESSED` reference site: both have different aggregate ID lists and count semantics. A missing reference deposit counts as assessed for coverage but must keep the existing comparison gate and zero observations.
- Keep the classifier's reference matching, warnings, top-level status, canonical observations, scoring contribution, and existing upload validation unchanged. Do not add full reference ROI measurements, raw masks, image bytes, contours, or a database field to the response.
- Document the two aggregates' scopes and the distinction among reference inspection coverage, reference suitability for comparison, process acceptance, and diagnostic Evidence Support /100. Historical response payloads without the new field must deserialize with `None`.

## Interfaces and data contracts

- Authorized additive top-level field on `ImageAnalysisResponse`: `reference_aggregate_measurements: AggregateMeasurements | null` (default `null` for older serialized responses and non-reference modes). The existing `aggregate_measurements` remains current-image-only.
- In `REFERENCE_IMAGE`, the field reuses the already calculated `AggregateMeasurements` with non-null coverage counts/status from DLK-M3-036. It contains derived bounded metrics and ROI ID lists only; no uploaded reference file or per-ROI geometry.
- `COMPLETE` reference inspection means all expected reference locations were assessed, not that a reference deposit exists at every location, the current image matches the reference, or the analysis is calibrated. Top-level `status` and `observations` retain their existing authority for diagnosis eligibility.
- Existing clients that ignore unknown response keys remain compatible. This task does not update Member 1's frontend TypeScript contract; a later coordinated UI task must add and render it.

## Allowed paths

- `backend/app/schemas/image.py`
- `backend/app/api/images.py`
- `backend/tests/integration/test_image_api.py`
- `backend/tests/unit/test_vision_measurement.py` only for a narrow legacy response-deserialization test if useful
- `docs/api/api-spec.md`
- `docs/architecture/region-inspection-improvement-plan.md` for a brief status note
- `.agents/handoff/tasks/DLK-M3-037-reference-inspection-coverage.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-036-review.md` (include planner-authored accepted review unchanged)

## Prohibited scope

Changing `defect_classifier.py`, segmentation/measurement algorithms, frontend files, case/report/AI prompt projection, database models or migrations, diagnostic weights or evidence semantics, partial score-bearing evidence, reference alignment, templates, new dependencies, remote Git operations, or main.

## Implementation guidance

1. Confirm the `backend-database` branch, accepted DLK-M3-036 review, and working tree. Read repository instructions and the existing reference-mode API tests. Preserve unrelated files.
2. Add failing API/schema tests that show the reference aggregate is missing. Cover successful reference analysis with complete current and reference coverage; a reliable current image with an unassessed reference image (`reference_aggregate_measurements.inspection_coverage_status=NONE` or `PARTIAL`, `status=UNRELIABLE`, no observations); and a confirmed missing reference deposit where reference inspection can be `COMPLETE` but analysis remains `UNRELIABLE` with no observations. Use controlled synthetic images and assert actual segmentation states rather than assuming a blank field is confirmed missing.
3. Verify `FEATURES_ONLY` and `PROCESS_LIMITS` return `reference_aggregate_measurements=null`, and an old serialized `ImageAnalysisResponse` without the field parses with `None`. Confirm current and reference counts/lists remain separate in the response.
4. Wire the already calculated `ref_agg` into the response and update API documentation. Keep the change narrow: this task adds exposure, not new classifier logic or altered scoring.
5. Inspect the final diff, complete this report, set queue status to implemented, and include the pending DLK-M3-036 accepted review in one scoped local commit after checks pass.

## Acceptance criteria

- [x] `REFERENCE_IMAGE` returns both existing current `aggregate_measurements` and separate non-null `reference_aggregate_measurements`, each with its own expected/assessed counts, coverage status, missing/unassessed ID lists, and metrics from the correct image.
- [x] Non-reference modes return `reference_aggregate_measurements=null`; legacy response data lacking the field parses with `None`.
- [x] A reliable current image with an unassessed reference image still returns `UNRELIABLE` and zero score-bearing observations while exposing the reference coverage failure and existing warnings.
- [x] A confirmed missing reference deposit counts as assessed in reference coverage but retains existing `UNRELIABLE` comparison gating and zero observations. Tests distinguish this from `UNASSESSED`.
- [x] Reference and current aggregates are never swapped or combined; old current aggregate behavior, upload validation, classifier output, and diagnostic scoring remain unchanged.
- [x] API documentation accurately distinguishes inspection coverage from reference suitability, acceptance, and Evidence Support /100; no frontend or persistence change is claimed.
- [x] Focused and full backend checks pass, only scoped files are locally committed, and no remote Git operation occurs.

## Verification

Run from repository root in PowerShell. For any database-backed tests in the full suite, use the existing safe disposable `TEST_DATABASE_URL` setup; never bypass its destination check or touch development/demo data.

1. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_image_api.py backend/tests/unit/test_vision_measurement.py -q --basetemp=backend/.task037-focused -p no:cacheprovider`
2. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task037-full -p no:cacheprovider`
3. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-037-reference-inspection-coverage.md`
4. `git diff --check` and inspect staged and unstaged changes before committing.

If a required check or safe disposable database is unavailable, record the exact blocker and report `blocked` instead of claiming implementation. Frontend checks are not required because frontend code is excluded.

## Planner decision boundaries

The additive reference aggregate field and its semantics above are authorized. Return to the planner before adding reference ROI geometry or image storage, changing public request fields, diagnosis eligibility, top-level status meaning, scoring, database storage, Member 1 frontend code, Member 2 diagnostic meaning, or any new dependency. Do not infer alignment or industrial reference suitability from coverage counts.

## Git instructions

Commit this task packet, completed implementation report, queue, pending accepted DLK-M3-036 review, and scoped code/tests/docs in one atomic local commit after checks pass. Do not stage unrelated files. Do not push, merge, rebase, create a PR, or change main.

Proposed commit message: `feat(vision): expose reference inspection coverage`

## Implementation report

### Summary

Exposed reference-image aggregate measurements as a separately scoped, optional additive field (`reference_aggregate_measurements: AggregateMeasurements | None = Field(default=None)`) on `ImageAnalysisResponse`. In `REFERENCE_IMAGE` mode with valid reference data, the field is populated from the already computed `ref_agg`, providing independent expected/assessed counts, inspection coverage status, missing/unassessed ROI ID lists, and summary metrics for the reference image. In non-reference modes (`FEATURES_ONLY` and `PROCESS_LIMITS`), the field explicitly serializes as `null`. Legacy serialized responses without the field deserialize safely as `None`. All diagnostic gating, conservative whole-image UNRELIABLE rules for unassessed or missing reference deposits, observation scoring, and upload validation remain strictly unchanged.

### Files changed

- `backend/app/schemas/image.py`: Added `reference_aggregate_measurements: AggregateMeasurements | None = Field(default=None)` to `ImageAnalysisResponse`.
- `backend/app/api/images.py`: Passed `reference_aggregate_measurements=ref_agg` into `ImageAnalysisResponse(...)`.
- `backend/tests/integration/test_image_api.py`: Added integration tests covering:
  - Reference mode returning non-null, separate `reference_aggregate_measurements` with distinct values from current aggregate;
  - Non-reference modes explicitly serializing `reference_aggregate_measurements` as `null`;
  - Reliable current image with unassessed reference image producing `UNRELIABLE`, zero observations, and reference coverage failure (`NONE`);
  - Confirmed missing reference deposit yielding `COMPLETE` reference inspection coverage but enforcing `UNRELIABLE` comparison gating;
  - Legacy serialized response payload deserialization default handling.
- `backend/tests/unit/test_vision_measurement.py`: Added unit test verifying `ImageAnalysisResponse` deserialization of legacy payloads without `reference_aggregate_measurements` as `None` and explicit reference payload as `AggregateMeasurements`.
- `docs/api/api-spec.md`: Added `reference_aggregate_measurements` to response JSON example, documented field semantics under additive measurement fields, and added dedicated section `Reference-Image Inspection Coverage (reference_aggregate_measurements)` distinguishing inspection completeness from reference comparison suitability, process acceptance, and diagnostic Evidence Support /100.
- `docs/architecture/region-inspection-improvement-plan.md`: Added Phase 1 implementation status note for increment DLK-M3-037.
- `.agents/handoff/tasks/DLK-M3-037-reference-inspection-coverage.md`: Recorded implementation status, completed acceptance criteria, and implementation report.
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-037 status to `implemented`.

### Decisions made

- Maintained clean separation between `aggregate_measurements` (current image) and `reference_aggregate_measurements` (reference image): both independently reflect the same configured expected ROI IDs without merging or swapping.
- Preserved existing conservative whole-image gating: a confirmed missing reference deposit reports `inspection_coverage_status=COMPLETE` because its absence was conclusively assessed, but continues to downgrade top-level analysis to `UNRELIABLE` with zero observations because a missing reference deposit cannot serve as a valid geometric comparison baseline.
- Preserved backward compatibility: `reference_aggregate_measurements` defaults to `None` for legacy clients and non-reference modes without altering database schemas or frontend contracts.

### Verification results

- Focused pytest suite: `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_image_api.py backend/tests/unit/test_vision_measurement.py -q --basetemp=backend/.task037-focused -p no:cacheprovider` -> `51 passed, 20 warnings in 1.96s`
- Full backend pytest suite: `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task037-full -p no:cacheprovider` -> `571 passed, 42 warnings in 59.41s`
- Task packet validation: `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-037-reference-inspection-coverage.md` -> `VALID`
- Whitespace validation: `git diff --check` -> Clean (code 0)

### Limitations and follow-up

- Frontend display and TypeScript types for `reference_aggregate_measurements` are deferred to a Member 1 frontend task.
- Per-ROI reference measurements, reference contours/masks, and reference image persistence remain outside scope and were not exposed.
- Automatic image registration/alignment between current and reference images remains deferred to Phase 3.

### Proposed commit message

`feat(vision): expose reference inspection coverage`
