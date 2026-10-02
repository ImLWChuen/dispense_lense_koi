---
task_id: DLK-M3-034
title: Expose bounded deposit outlines for trustworthy region overlays
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-033]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-034: Bounded deposit outlines

## Objective

Return display-ready outlines of reliably detected deposits from the existing ROI segmentation pipeline. This is the backend geometry needed for the later image workbench. The outline is a visual aid, not a new measurement, acceptance decision, or diagnostic observation.

## Current evidence

- DLK-M3-033 is accepted at local commit `3d1fb6f5adb6d50a975704527f21f23334549546`; its uncommitted review record and QUEUE.md acceptance update belong to this handoff commit.
- `segment_roi` in `backend/app/services/vision/segmentation.py` returns a selected `deposit_contour` in coordinates local to the expanded analysis window. Some UNRELIABLE results also carry a contour, so contour existence alone is not evidence of a reliable deposit.
- `backend/app/api/images.py` knows the normalized expected ROI, its pixel target and expanded window, the full image dimensions, and the resulting `RoiMeasurement`. It currently discards the contour after measurement.
- `RoiMeasurement` has no outline field. `ImageAnalysisResponse.image_dimensions` contains the current image dimensions. The reference image measurements are used internally for comparison and are not returned as an overlay surface.
- `frontend/types/image.ts` and `frontend/components/diagnosis/ImageUpload.tsx` consume the current response; this task only adds an optional backend field. The frontend will be assigned separately under Member 1 ownership.
- The broader draft roadmap is `docs/architecture/region-inspection-improvement-plan.md`. The repeated-layout versus varied-product decision is pending and does not affect this geometry task.
- Existing unrelated `.agents.zip` and `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md` are excluded from staging.

## Requirements

- Add an optional `deposit_outline_normalized` field to each `RoiMeasurement`. For DETECTED regions with a reliable selected outer contour, it contains an ordered polygon of full-current-image normalized points (`x`, `y`, each in `[0,1]`). For MISSING and UNASSESSED regions it is null, even if segmentation returned a candidate contour.
- Convert each point from analysis-window-local coordinates to full-image coordinates using the actual expanded window origin, then normalize by the decoded current image width and height. A target ROI's origin is not the contour origin. The geometry must align when the image is scaled in the UI.
- Polygon must have at least three distinct finite points and no more than 128 points. Preserve contour order. Use deterministic bounded approximation; do not slice the first 128 points, substitute a bounding rectangle, or pretend an omitted outline is an exact contour. If safe approximation within the cap is impossible, return null with a region-specific overlay warning. The geometry may be approximate and must not change numeric measurements.
- Keep all emitted normalized points inside the image bounds; do not silently clamp a substantially out-of-bounds contour into a plausible overlay. Treat invalid/degenerate geometry as unavailable and add a warning.
- Outline unavailability must not change `inspection_status`, `is_missing`, aggregate values, `AnalysisStatus`, observation scores, or acceptance logic. An otherwise reliable deposit can remain DETECTED without an outline.
- Add a warning that explains missing overlay geometry when a DETECTED region has no publishable outline. Preserve existing segmentation and reliability warnings. Ensure the warning reaches top-level response warnings because existing clients may not read the new field.
- Keep output bounded: never serialize raw masks, OpenCV arrays, contours without the point cap, or reference-image outlines in this increment. Do not embed uploaded images in JSON.

## Interfaces and data contracts

Authorized additive API contract: `RoiMeasurement.deposit_outline_normalized: list[NormalizedPoint] | null`, default null for legacy serialized results. `NormalizedPoint` has finite `x` and `y` in `[0,1]`; use a typed Pydantic model. Coordinates use the complete current image, with `(0,0)` at its top-left and `(1,1)` at its bottom-right. This field represents the selected *outer* contour; interior holes/bubble boundaries are not included. It is for drawing only and may be simplified. Document these limits in `docs/api/api-spec.md`.

Preserve endpoint, request profile, existing response fields, current/reference evidence semantics, global statuses, and all numeric units. No storage or database changes. Existing consumers may ignore the new field.

## Allowed paths

- `backend/app/schemas/image.py`
- `backend/app/api/images.py`
- `backend/app/services/vision/measurement.py` if a small helper belongs there
- `backend/app/services/vision/overlay.py` if a separate pure geometry helper is clearer
- `backend/tests/unit/test_vision_*.py`
- `backend/tests/integration/test_image_api.py`
- `backend/tests/fixtures/synthetic_images.py` only if needed for deterministic geometry fixtures
- `docs/api/api-spec.md`
- `docs/architecture/region-inspection-improvement-plan.md` for a brief increment status note only
- `.agents/handoff/tasks/DLK-M3-034-bounded-deposit-outline.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-033-review.md` (include the planner-authored accepted review unchanged)

## Prohibited scope

Frontend edits, automatic site detection, alignment, reusable profiles/templates, reference-image overlay display, mask serialization, storing image/geometry, new models/dependencies, changed segmentation thresholds/algorithms, new diagnostic rules/scores, partial score-bearing evidence, DB migration, real-world accuracy claims, remote Git operations, and changes to main.

## Implementation guidance

1. Verify `backend-database`, exact parent commit, accepted prerequisite, and safe working tree. Read instructions and the scoped source/tests. Preserve unrelated files and planner-authored review/queue updates.
2. Add tests for coordinate transformation with a nonzero window origin and for a scaled synthetic image. Confirm the new behavior fails on the old implementation before implementing it.
3. Implement the typed additive field and a bounded geometry conversion path. Prefer a small pure helper that can be unit tested; keep geometry extraction independent from diagnostic classification.
4. Publish outlines only for DETECTED current-image regions. Exercise MISSING, UNASSESSED with candidate contour, missing contour, degenerate/out-of-bounds contour, and above-cap complexity. Avoid emitting false outlines.
5. Add at least one real synthetic-image API regression that checks a known off-center deposit's outline location against the full-image coordinates and verifies the point cap. Check that existing measurements and observations remain unchanged for the same fixture.
6. Document the field, coordinate convention, approximation and omission behavior. Inspect frontend consumers read-only for compatibility. Do not edit Member 1 files.
7. Complete the report and commit only after required verification succeeds.

## Acceptance criteria

- [x] A reliable, off-center deposit produces a non-null ordered outer outline in full-image normalized coordinates, aligned after changing source image resolution.
- [x] Every emitted polygon has 3–128 distinct finite points in `[0,1]`; complex/invalid contours never create unbounded JSON or fabricated shapes.
- [x] MISSING and UNASSESSED regions emit null outlines, including UNASSESSED results that contain a candidate contour.
- [x] A DETECTED region with unavailable geometry remains DETECTED; a specific top-level warning explains why its overlay is unavailable.
- [x] The new field defaults to null for old serialized measurements; existing request/response behavior, numeric measurements, and diagnostic observations remain intact.
- [x] Tests cover nonzero window offset, resolution scaling, point bound, failure/unknown states, and a real synthetic image through the API.
- [x] Documentation states the outline is approximate display geometry and does not establish volume, internal defects, or root cause.
- [x] No unrelated files or generated artifacts are staged or committed; no real-world accuracy claim is made.

## Verification

Run from repository root in PowerShell. Use existing disposable `TEST_DATABASE_URL` safeguards for all database-backed tests; never run them against development records or bypass the bootstrap.

1. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_segmentation.py backend/tests/unit/test_vision_measurement.py backend/tests/integration/test_image_api.py -q --basetemp=backend/.task034-focused -p no:cacheprovider`
2. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task034-full -p no:cacheprovider`
3. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-034-bounded-deposit-outline.md`
4. `git diff --check`

If a required check cannot run, record the exact blocker and do not claim the task implemented. Frontend lint/build are not required because frontend code is excluded.

## Planner decision boundaries

The optional outline field and geometry conversion above are authorized for this Member 3 task. Return to the planner before changing other public fields, request validation/limits, reference-image output structure, score semantics, persistence, dependencies, frontend ownership, or scope. Implementation choices for contour simplification inside the stated point and validity bounds belong to Gemini.

## Git instructions

Create one atomic local commit after checks pass. Include the pending accepted DLK-M3-033 review, QUEUE.md, this packet, scoped code/tests/docs only. Preserve unrelated work. Do not push, merge, rebase, create a PR, or change main.

Proposed commit message: `feat(vision): expose bounded deposit outlines for region overlays`

## Implementation report

### Summary

- Implemented `NormalizedPoint` Pydantic model in `backend/app/schemas/image.py` enforcing finite coordinates in `[0.0, 1.0]`. Added additive `deposit_outline_normalized: list[NormalizedPoint] | None = Field(default=None)` to `RoiMeasurement`.
- Created pure geometry service in `backend/app/services/vision/overlay.py` with `extract_deposit_outline`:
  - Translates window-local coordinates to full-image pixel coordinates via the analysis window origin (`(window_roi.x + x_local) / width`), ensuring accurate alignment across image resolutions.
  - Caps polygon vertices to 3–128 finite distinct points using deterministic Douglas-Peucker approximation (`cv2.approxPolyDP`) without slicing or bounding box substitutions.
  - Restricts outline emission strictly to `DETECTED` current-image regions; `MISSING` and `UNASSESSED` regions strictly emit `null` outlines even if candidate contours exist.
  - Rejects substantially out-of-bounds, degenerate (<3 distinct points), or zero-perimeter geometry without silent fake clamping.
  - Resolved Review Finding R1: Enforced strict distinctness across all published polygon vertices. Unified coordinate key hashing `(round(x, 6), round(y, 6))` across consecutive deduplication, closing-point popping, and distinctness checking. Explicitly rejects nonconsecutive duplicate vertices (such as `[A, B, C, A, D]`) with specific warning `ROI '{roi_id}' deposit outline unavailable (nonconsecutive duplicate vertices detected).`
  - Preserves `DETECTED` region status and diagnostic observations unchanged when an outline is omitted due to nonconsecutive duplicate vertices or unavailable geometry.
  - Returns explicit overlay warnings on `DETECTED` regions when geometry is unavailable, without downgrading overall analysis status or changing diagnostic observations.
- Integrated outline extraction and top-level warning propagation in `backend/app/api/images.py`. Reference image measurements strictly omit outlines.
- Documented data contracts, display-aid nature, and coordinate conventions in `docs/api/api-spec.md` and recorded increment progress in `docs/architecture/region-inspection-improvement-plan.md`.

### Files changed

- `backend/app/schemas/image.py`: added `NormalizedPoint` schema and `deposit_outline_normalized` field to `RoiMeasurement`.
- `backend/app/services/vision/overlay.py`: implemented `extract_deposit_outline` helper with bounded approximation, window-to-full-image translation, and strict nonconsecutive duplicate vertex rejection.
- `backend/app/api/images.py`: integrated outline extraction and warning propagation in `_sync_analyze_image`.
- `backend/tests/unit/test_vision_overlay.py`: added comprehensive unit tests for window offset translation, resolution scaling invariance, complex contour capping, missing/unassessed omission, degenerate warnings, nonconsecutive duplicate rejection (R1), closing point popping, and consecutive deduplication.
- `backend/tests/integration/test_image_api.py`: added integration tests verifying real synthetic off-center deposit outlines, null outlines for missing/unassessed regions, unavailable outline warnings without analysis status downgrade, and nonconsecutive duplicate vertex preservation (R1).
- `docs/api/api-spec.md`: documented the `deposit_outline_normalized` contract, coordinate conventions, approximation boundaries, and nonconsecutive duplicate rejection.
- `docs/architecture/region-inspection-improvement-plan.md`: recorded Phase 2 progress for increment DLK-M3-034.
- `.agents/handoff/QUEUE.md`: synchronized DLK-M3-034 status to `implemented` with R1 resolution details.
- `.agents/handoff/tasks/DLK-M3-034-bounded-deposit-outline.md`: completed implementation report and set status to `implemented`.

### Decisions made

- Window offset translation: window coordinates are converted to global image coordinates using `window_roi.x` and `window_roi.y` (the analysis window origin), not `target_roi.x`/`y`, guaranteeing that contours segmented within expanded analysis windows properly align when rendered over the full image.
- Bounded approximation: used binary search with `cv2.approxPolyDP` across epsilon values to find the finest valid approximation yielding 3–128 points, avoiding slicing or bounding box approximation.
- Strict vertex distinctness (R1): all polygon vertices must be unique. Normalized coordinates use consistent 6-decimal rounded keys for consecutive deduplication, closing point stripping, and distinctness validation. Contours containing repeated vertices are safely omitted with an explanatory warning rather than arbitrarily mutated.
- Non-degrading unavailability: unavailable outline geometry on a `DETECTED` deposit emits an explanatory warning in `inspection_warnings` and top-level `warnings` while leaving `inspection_status = DETECTED` and diagnostic observations intact. Old clients and non-visual workflows remain unaffected.
- Reference image omission: reference image measurements do not serialize outlines in this increment to keep response payloads small and bounded.

### Verification results

- Verification commands:
  - Focused test suite: `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_segmentation.py backend/tests/unit/test_vision_measurement.py backend/tests/unit/test_vision_overlay.py backend/tests/integration/test_image_api.py -q --basetemp=backend/.task034-focused -p no:cacheprovider` -> `52 passed, 20 warnings in 2.00s`
  - Full test suite: `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task034-full -p no:cacheprovider` -> `543 passed, 42 warnings in 57.32s`
  - Task packet validation: `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-034-bounded-deposit-outline.md` -> `VALID: .agents\handoff\tasks\DLK-M3-034-bounded-deposit-outline.md`
  - Git whitespace diff check: `git diff --check` -> clean (exit code 0)

### Limitations and follow-up

- Outlines represent the outer deposit contour; interior holes and bubbles are omitted from the outline polygon (bubble details remain available in `bubble_details`).
- Visual frontend rendering on the image canvas/workbench remains scheduled for Member 1 ownership.
- Reusable profile templates and automatic site alignment remain scheduled for subsequent increments.

### Proposed commit message

`fix(vision): reject nonconsecutive duplicate vertices in deposit outlines`
