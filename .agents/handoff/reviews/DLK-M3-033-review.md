---
task_id: DLK-M3-033
reviewed_commit: 3d1fb6f5adb6d50a975704527f21f23334549546
decision: accepted
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-033

## Decision

Accepted at `3d1fb6f5adb6d50a975704527f21f23334549546`. R1, including the all-omitted boundary, is resolved. No further actionable findings in the scoped correction. Historical findings below are retained for traceability.

## Final correction review of 3d1fb6f

- Current and reference omitted-ID warning collection now runs outside nonempty-list branches. Empty current lists and empty/None reference lists preserve each expected ID and its missing-measurement explanation.
- New regressions assert both expected IDs, empty observations, FEATURES_ONLY neutrality, and calibrated-mode UNRELIABLE status.
- Prior warning-collection fixes remain intact; the correction does not change segmentation, scoring, frontend, dependencies, or storage.
- Gemini reports 66 focused tests and 529 backend tests passed, with task validator VALID. These results were inspected in the implementation report, not independently rerun under the PROJECT.md planner/reviewer role split.
- Reviewer verified exact commit, scoped diff, backend-database branch, and clean committed whitespace check.
- Review and queue updates are left uncommitted. No remote Git operation performed.

## Historical correction review of 028c857 (resolved by 3d1fb6f)

Verified by source/test inspection: FEATURES_ONLY now retains actual segmentation failure explanations; multiple unassessed reference measurements are collected; simultaneous current/reference failures preserve both sets. The three new regressions exercise these cases without weakening status/observation assertions.

Remaining R1 (P2), `backend/app/services/vision/defect_classifier.py:37-53,58-83`: omitted-ID collection is nested under the nonempty measurement branches. For `roi_measurements=[]` with aggregate.unassessed_roi_ids containing expected IDs, only a generic no-measurements explanation is collected. For `reference_measurements=[]` with reference_aggregate.unassessed_roi_ids populated, even the reference IDs are lost; the response contains only the generic reference requirements warning. The latter aggregate is not exposed separately by the API response. This is the all-omitted boundary of the explicitly required omitted-measurement contract, not a scoring bypass or a demonstrated failure of the normal image loop.

Move expected-but-omitted ID collection outside the nonempty-list branches for both current and reference data. Compute IDs safely from empty/None lists. Preserve the generic warnings as useful context and all existing mode gates. Add unit regressions for empty current measurements and empty reference measurements with populated expected unassessed IDs; assert every ID has an explicit missing-measurement explanation and observations remain empty. Rerun required checks and update the report.

Gemini reports correction verification: 64 focused tests, 527 backend tests, task validator VALID. Tests were not rerun by the reviewer under PROJECT.md's role split. Committed whitespace check independently passed. Changes remain scoped; no remote operation performed.

## Original R1 — P2: Collect region reliability explanations before early returns

Location: `backend/app/services/vision/defect_classifier.py:35-65` and `247-264`.

- FEATURES_ONLY returns before collecting inspection_warnings. A uniform uninspectable image exposes only an aggregate unassessed-ID summary and the generic uncalibrated message; the actual segmentation reason remains in the additive measurement field that existing clients do not display.
- REFERENCE_IMAGE returns on the first unassessed reference measurement, hiding the remaining affected reference IDs and reasons. Reference measurements are not returned by ImageAnalysisResponse, so those omitted explanations cannot be recovered by the caller.
- An unassessed current measurement also triggers a return before reference warnings are collected.

The packet requires affected IDs and reasons in top-level warnings for existing clients. The current frontend renders result.warnings in ImageUpload.tsx, making this an observable guidance gap rather than a scoring defect.

Correction: collect and deduplicate all applicable current and reference reliability warnings before mode/status early returns. Preserve FEATURES_ONLY as UNCALIBRATED with no observations, and preserve calibrated-mode UNRELIABLE gating. Include expected-but-omitted measurement IDs with an explicit missing-measurement reason. Do not introduce partial evidence or frontend changes.

Regression coverage: a real uniform FEATURES_ONLY upload must expose the ROI ID and actual failure reason at top level; multiple unassessed reference ROIs must all be named with their reasons; simultaneous current/reference failures must retain both sets of explanations. Rerun the task's focused and full checks and update the implementation report.

## Evidence reviewed

- Exact local commit and parent diff; branch is backend-database.
- Schema defaults safely mark legacy measurements UNASSESSED.
- Measurement mapping retains segmentation warnings and prevents UNASSESSED from setting is_missing.
- Aggregates separate omitted/unassessed from missing and exclude unassessed measurements from coverage/CV.
- Explicit current/reference UNASSESSED gates prevent observations despite high numeric quality.
- Added real-image API regressions cover uniform, mixed, and genuine empty-site cases. Existing tests were retained.
- Committed whitespace check passed during review.

## Verification boundary

Gemini reports 61 focused tests and 524 full-backend tests passed, plus a valid task packet. These are implementer-reported results, not independently rerun in this review: PROJECT.md assigns execution/testing to Gemini. Review used source, tests, documentation, and Git inspection. No real-world image accuracy validation is claimed.

## Follow-up

DLK-M3-033 is accepted; no further correction is required. Overlays, templates/alignment, partial evidence, and real-image evaluation remain subsequent scope. No next task was generated. No push, merge, PR, or changes to main are authorized by this review request.
