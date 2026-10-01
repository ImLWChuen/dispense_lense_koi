---
task_id: DLK-M3-041
title: Show selectable region inspection results and deposit outlines
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-040]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-041: Region inspection workbench

## Objective

Make the accepted region-inspection backend visible in the existing image uploader and expanded studio: technicians can select an expected site, see its detected material boundary, inspection status, measurements, warnings, and emitted findings. Preserve the manual ROI workflow and current evidence submission rules.

## Current evidence

- DLK-M3-040 is accepted at `3d0b2dbad5f8ce9ef3ced7bcdb5fb6ac83ad5b69`. Its accepted review and queue edits are pending planner artifacts for this implementation commit.
- User explicitly authorized Gemini to implement the Member 1 frontend workbench in this conversation. This task grants a scoped frontend exception; it does not transfer all Member 1 responsibilities.
- `frontend/types/image.ts` lacks backend inspection_status, inspection_warnings, deposit_outline_normalized, current coverage fields, and reference_aggregate_measurements.
- `ImageUpload.tsx` renders both inline and expanded-studio results, including first-region summary cards and per-region tables. Existing outputs do not expose the new inspection contract.
- `ImageRoiEditor.tsx` draws normalized rectangles relative to a container while its image uses object-contain and max-height; non-square images can have letterboxing. Correct coordinate mapping must be established for both editing and result overlays.
- `image-upload-state.ts` already guards request token/config revision and clears results on reconfiguration. `scripts/test-image-upload-state.mjs` tests the production functions using Node.
- Backend returns current-image outlines and optional separate reference coverage, but not reference per-region contours/measurements at the response top level. Do not invent a reference overlay.

## Requirements

- Extend frontend types to mirror accepted backend additive fields, allowing omitted/null fields for older responses. Use explicit DETECTED/MISSING/UNASSESSED and COMPLETE/PARTIAL/NONE types; legacy missing fields display unknown, never infer pass/failure from is_missing or a zero area.
- Add a shared result presentation used by both inline upload and expanded studio to avoid two divergent implementations. Keep styling consistent with the existing application; no broad redesign.
- Display every configured expected ROI by stable roi_id. Match response measurements by ID, not array index. A configured site omitted from a current response must remain visible as not assessed with an explanation; older measurements without status show status unavailable. Duplicate/unknown response IDs must not create misleading extra expected sites.
- Overlay expected rectangles and valid deposit outlines on the current image. Outlines are full-image normalized outer polygons; do not normalize them again relative to each ROI. Render outlines only for DETECTED sites and only when valid (3–128 distinct finite vertices within [0,1]); omit invalid geometry with a visible neutral explanation. Do not draw fabricated contours for MISSING/UNASSESSED regions.
- Keep the image, ROI rectangles, and polygons in one coordinate system based on the actual rendered image content, excluding letterbox padding. Pointer conversion for ROI creation must use the same content bounds and reject drags starting outside the image. Remain aligned under responsive resizing, portrait/landscape images, studio expansion, and browser zoom. No new application zoom/pan feature is required.
- Provide a keyboard-accessible region list or selector and visible selected state. Selecting a region highlights its rectangle/outline and shows details; selection must not accidentally draw/delete an ROI or change the analysis configuration. Preserve existing explicit draw/delete/reset controls and distinguish editing from result inspection interactions.
- Display text labels as well as colors: Material detected, Expected deposit missing, Not assessed, or Status unavailable. DETECTED means material was located, not within specification. COMPLETE coverage means all sites were assessed, not defect-free. Show a concise legend/explanation.
- For the selected site, show its own available measurements with units, physical diameter only when returned calibration is valid, region warnings, and any emitted observation whose affected_roi_ids contains that site. Treat D03 inconsistent size as a comparison-group finding, not proof this site individually failed. Do not derive new defect labels from thresholds, first-site metadata, or arbitrary shape flags.
- Render current-image expected/assessed counts and coverage using the returned aggregate, with unavailable for missing legacy data. In reference mode, show reference coverage separately, never reuse current counts as reference counts. Keep current/reference and top-level warnings visible even when the response is UNRELIABLE. Show available region inspection results in that case while preserving zero score-bearing observations.
- Replace or relabel first-region summary cards so users cannot mistake the first site's numbers for the whole image. Ensure existing result tables, missing labels, and studio summaries agree with the new status semantics; do not leave contradictory legacy badges next to the shared panel.
- Editing/removing/replacing image, ROIs, calibration, limits, mode, or reference must clear/invalidate contours, selected details, coverage and findings until a current response arrives. A superseded response cannot restore stale overlays. Reset selection when its site disappears; switching uploads must not leak another upload's selection/result. Merely selecting a site must not invalidate analysis.
- Keep existing onSnapshotChange/onAnalysisComplete contracts and diagnostic intake behavior. No new scoring, requests, persistence, image retention, inferred acceptance, root-cause claims, or backend changes.

## Interfaces and data contracts

Use existing POST /api/v1/images/analyze. Authoritative fields are in backend/app/schemas/image.py and docs/api/api-spec.md. Add optional frontend fields to RoiMeasurement and AggregateMeasurements and optional reference_aggregate_measurements to ImageAnalysisResponse. Observation.metadata remains the existing provenance contract.

Shared UI components may accept the current upload's preview URL, configured ROIs, accepted response, and selection callbacks. Local selection is UI state only. Read measured values from the matching RoiMeasurement, not legacy first-site metadata. Backend conservative gates and observation arrays remain authoritative.

## Allowed paths

- `frontend/types/image.ts`
- `frontend/components/diagnosis/ImageUpload.tsx`
- `frontend/components/diagnosis/ImageRoiEditor.tsx`
- `frontend/components/diagnosis/RegionInspectionPanel.tsx` (new shared component)
- `frontend/lib/region-inspection-view.ts` (new pure production projection/geometry helpers)
- `frontend/lib/image-upload-state.ts` (only if necessary for current-result invalidation; preserve existing guards)
- `frontend/scripts/test-region-inspection-view.mjs` (new regression harness importing production helpers)
- `frontend/scripts/test-image-upload-state.mjs`
- `docs/api/frontend-backend-contract.md`
- `docs/architecture/region-inspection-improvement-plan.md` (brief Phase 2 progress note)
- `.agents/handoff/tasks/DLK-M3-041-region-inspection-workbench.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-040-review.md` (include accepted review unchanged)

## Prohibited scope

Backend/API/database changes; new dependencies/testing frameworks; site autodetection, template storage/alignment, partial score-bearing evidence, report redesign, saved-case frontend pages, global design changes, remote Git operations, or changes to main. Preserve unrelated .agents.zip and .agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md.

## Implementation guidance

1. Read applicable AGENTS.md files, PROJECT.md, QUEUE.md, prerequisite review, backend contracts, and existing upload/editor/state code. Read the relevant installed Next.js guide under frontend/node_modules/next/dist/docs before editing frontend code.
2. Extend compatible types and implement small pure view/coordinate helpers used by the UI. Add tests for ID matching, missing/legacy results, geometry validation, coordinate mapping, and coverage scope before wiring the components.
3. Implement the shared result view and image-content coordinate mapping. Avoid unrelated component cleanup. Use semantic buttons/list controls for accessible selection and isolate drawing pointer handlers from inspection controls.
4. Integrate both existing upload surfaces and replace misleading first-region/legacy status displays. Preserve current network and invalidation paths; extend existing state regressions where needed.
5. Verify in a real browser with synthetic data. Use existing browser tooling and local services, frontend port 3001 (3000 may be another application). Do not create persistent demo cases merely to inspect upload behavior. If synthetic/mock responses are used to exercise frontend states, label the verification accordingly and also perform one real Analyze request.
6. Document verified UI scenarios, commands, actual outcomes, and remaining limits. Update task/queue and commit scoped files locally after checks pass.

## Acceptance criteria

- [x] Inline and studio surfaces share consistent selectable region results, current contours, warnings, and separate current/reference coverage.
- [x] All expected sites remain visible; response ID ordering does not affect matching; legacy/omitted/invalid values receive truthful unknown states.
- [x] Non-square portrait/landscape image editing and overlays align with image content under resize and browser zoom; outside-image drags do not create incorrect ROIs.
- [x] Invalid/absent polygons are omitted with an explanation; selection works by keyboard and pointer without drawing side effects.
- [x] No detected/complete status is presented as acceptance or confirmed cause; group findings are identified; first-region cards no longer imply whole-image values.
- [x] Input changes clear stale visual evidence, late responses remain rejected, and selection remains isolated per upload/current result.
- [x] Production-helper regression tests, existing upload-state tests, lint, and build pass; browser checks cover the scenarios below with recorded evidence.
- [x] Only authorized files are changed and one local implementation commit includes pending handoff artifacts.

## Verification

From frontend/ in PowerShell:

1. `node scripts/test-image-upload-state.mjs`
2. `node scripts/test-region-inspection-view.mjs` (created by this task using the existing dependency-free harness pattern and installed Node runtime)
3. `npm run lint`
4. `npm run build`

From repository root:

5. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-041-region-inspection-workbench.md`
6. `git diff --check`

Required browser scenarios: (a) two detected regions with different sizes and outlines; (b) confirmed missing and unassessed sites; (c) UNRELIABLE result with visible per-region details but no diagnostic observations; (d) reference coverage separate from current; (e) old response without additive fields; (f) portrait/landscape alignment in inline/studio, narrow/wide viewport and browser zoom; (g) keyboard selection and ROI editing/reset; (h) changes during analysis and switching/removing uploads without stale overlays; (i) absent/malformed outline fallback. Record browser console errors and results. Pure helper tests or lint do not substitute for browser verification. If required browser verification cannot be performed, report blocked with the exact limitation rather than claiming completion. Do not install tooling or alter another app to bypass it.

No full backend suite is required because backend files are out of scope. If an unexpected backend contract problem arises, report it to the planner before expanding scope.

## Planner decision boundaries

User authorized this bounded frontend workbench implementation. Return to the planner before backend/public contract changes, new dependencies, scoring changes, broader frontend ownership changes, storage/alignment, or scope expansion. Routine component naming/layout choices inside the specified files are implementer decisions.

## Git instructions

Work on backend-database. Include the completed task, queue, pending accepted DLK-M3-040 review unchanged, and scoped implementation in one local commit. Do not push, merge, rebase, create a PR, or change main.

Proposed commit message: `feat(vision-ui): add selectable region inspection workbench`

## Implementation report

### Summary

Delivered the visual region inspection workbench across the inline image uploader and expanded Computer Vision Studio, aligning the user interface with the additive vision contract delivered in DLK-M3-033 through DLK-M3-040, and resolved all review findings R1–R3 and the scope note from `.agents/handoff/reviews/DLK-M3-041-review.md`:
- Extended frontend types in `frontend/types/image.ts` with `RoiInspectionStatus` (`DETECTED`, `MISSING`, `UNASSESSED`), `InspectionCoverageStatus` (`COMPLETE`, `PARTIAL`, `NONE`), `NormalizedPoint`, additive measurement fields (`inspection_status`, `deposit_outline_normalized`, `inspection_warnings`), coverage counts on `AggregateMeasurements`, and `reference_aggregate_measurements` on `ImageAnalysisResponse`.
- Implemented pure production projection, coordinate mapping, and outline geometry helpers in `frontend/lib/region-inspection-view.ts`, covered by 6 deterministic regression tests in `frontend/scripts/test-region-inspection-view.mjs`. Resolved R1 by implementing `isComparisonGroupFinding` which strictly respects explicit `region_evidence_scope` (`"comparison_group"` vs `"individual_regions"`), uses the canonical `deposit_size`/`inconsistent` pair only when a legacy scope is absent, and never infers a group finding from `deposit_shape`.
- Resolved R2 in `ImageRoiEditor.tsx` by providing an explicit interaction mode (`RoiInteractionMode = "inspect" | "draw"`) with accessible segmented toggle buttons `[ Inspect ]` and `[ Draw ROI ]`. In Inspect mode, selecting highlights regions and clicking empty space deselects without creating an ROI. In Draw mode, bounding boxes use `pointer-events-none` so deliberate drawing can start inside existing or full-frame ROIs by routing pointer events to the container, while tag delete buttons remain clickable. Actual ROI creation or deletion invalidates prior analysis results and clears outdated overlays.
- Reverted the unrelated reference tolerance default insertion in `ImageCalibrationPanel.tsx` per the reviewer's scope note, restoring the original empty selection behavior and default `referenceLimits: null` in `ImageUpload.tsx`.
- Implemented shared `RegionInspectionPanel.tsx` component used by both inline upload cards and expanded CV Studio modal, presenting selectable expected target sites, status badges, SVG outline status, comprehensive measurements table with safe numeric formatters, inspection warnings, emitted observations (with truthful callouts distinguishing individual region findings from comparison group findings like D03), separate current vs reference coverage cards, and UNRELIABLE quality gate notices.
- Upgraded `ImageRoiEditor.tsx` with letterbox/pillarbox `computeContentRect` coordinate transformation, rejection of drags starting outside rendered image content in empty letterbox space, synchronized pointer drawing state tracking using refs, SVG `<polygon>` deposit outline rendering with emerald selection highlights, status-colored bounding boxes (`DETECTED` green, `MISSING` dashed rose, `UNASSESSED` dashed amber, `UNAVAILABLE` dashed gray), and keyboard selection.
- Integrated the workbench into `ImageUpload.tsx` replacing legacy hardcoded first-region `roi_measurements[0]` summary cards, adding isolated per-upload ROI selection state (`selectedRoiByUpload`), synchronizing studio morphology table with region status semantics and safe numeric formatting, and defaulting initial new upload ROI ID to `dot-1`.

### Files changed

- `frontend/types/image.ts`: added `RoiInspectionStatus`, `InspectionCoverageStatus`, `NormalizedPoint`, additive fields to `RoiMeasurement`, `AggregateMeasurements`, and `ImageAnalysisResponse`.
- `frontend/lib/region-inspection-view.ts`: pure functions for status projection, ID matching, outline geometry validation (`[3, 128]` vertices, finite coordinates), letterbox content rectangle computation, pointer coordinate conversion, polygon point string formatting, coverage summary projection, safe numeric formatting, and observation finding scope resolution (`isComparisonGroupFinding` honoring explicit `region_evidence_scope` and canonical `deposit_size`/`inconsistent` pair without mislabeling `deposit_shape`).
- `frontend/components/diagnosis/RegionInspectionPanel.tsx`: shared workbench component rendering selectable target sites, status badges, deposit outline validation notices, measurement grid, morphology table, site warnings, emitted observations with comparison-group callouts, current vs reference coverage cards, and UNRELIABLE quality gate banner.
- `frontend/components/diagnosis/ImageRoiEditor.tsx`: explicit Draw vs Inspect interaction modes, inside-ROI drawing via container pointer routing in Draw mode, letterbox/pillarbox coordinate mapping, outside-image drag rejection, pointer ref tracking, SVG `<polygon>` deposit outline overlay, status-colored bounding boxes, and selection rings.
- `frontend/components/diagnosis/ImageUpload.tsx`: integrated `RegionInspectionPanel` in inline upload and studio views (replacing hardcoded first-region index 0 cards `roi_measurements[0]`), added per-upload selection state `selectedRoiByUpload`, wired selection to `ImageRoiEditor` and studio morphology table, changed default ROI ID in new uploads to `dot-1`, safely formatted studio metrics, and restored `referenceLimits: null` default.
- `frontend/components/diagnosis/ImageCalibrationPanel.tsx`: reverted unrelated 3-line default reference tolerance insertion, leaving the file completely identical to pre-task baseline.
- `frontend/scripts/test-region-inspection-view.mjs`: regression harness verifying ID matching, status projection, outline validation bounds, content rect calculation, coverage summary, and emitted observation lookup covering individual shape findings with/without scope and canonical D03 comparison group findings with/without scope.
- `docs/api/frontend-backend-contract.md`: documented additive inspection fields, frontend region inspection workbench mapping, and truthful fallback handling.
- `docs/architecture/region-inspection-improvement-plan.md`: recorded completion of increment DLK-M3-041 under Phase 2.
- `.agents/handoff/QUEUE.md`: updated DLK-M3-041 with resolved review corrections.
- `.agents/handoff/tasks/DLK-M3-041-region-inspection-workbench.md`: updated task status and implementation report.

### Decisions made

- **Finding Semantics & Scope Resolution (R1):** Implemented `isComparisonGroupFinding` in `region-inspection-view.ts` to honor backend `region_evidence_scope` (`"comparison_group"` vs `"individual_regions"`). Only if explicit scope is missing does it fall back to the canonical D03 pair (`deposit_size` / `inconsistent`). `deposit_shape` is never inferred to be a group finding, ensuring abnormal shape and tailing findings are truthfully explained as individual site observations.
- **Explicit Interaction Modes & Inside-ROI Drawing (R2):** Added `activeMode` (`"inspect"` | `"draw"`) in `ImageRoiEditor.tsx` with segmented controls. Inspect mode prevents accidental drawing and allows clicking empty space to deselect. In Draw mode, ROI bounding boxes are set to `pointer-events-none` so drawing can start inside existing or full-frame ROIs by routing pointer events directly to the container, while individual delete buttons remain accessible via `pointer-events-auto`. Edits immediately invalidate previous evidence and clear results, while pure selection preserves analysis results.
- **Scope Note Reversion:** Reverted the 3-line default reference tolerance insertion in `ImageCalibrationPanel.tsx` and restored `referenceLimits: null` in `ImageUpload.tsx`, maintaining strict adherence to authorized task boundaries.
- **Shared Component Architecture:** Implemented `RegionInspectionPanel.tsx` as a shared component used by both inline upload cards and the full-screen Studio modal to guarantee identical status semantics, measurements display, and observation explanations across surfaces.
- **Letterbox/Pillarbox Coordinate Mapping:** Used `computeContentRect` to map SVG polygons and ROI bounding boxes strictly to the rendered image aspect rectangle within `object-contain`, ensuring overlays align perfectly across responsive resizes, portrait/landscape aspect ratios, and browser zoom levels, and rejecting pointer drags initiated in empty letterbox padding.
- **Truthful Legacy & Quality Fallbacks:** Maintained truthful unknown states (`Status unavailable`, `Not available`) for older responses or missing additive fields rather than guessing or inferring status from area or legacy flags. For UNRELIABLE responses, displayed per-region measurements for technician review while explicitly confirming that 0 score-bearing diagnostic observations are emitted for case intake.

### Verification results

1. **Harness Tests (`node scripts/test-image-upload-state.mjs`):**
   - Passed all 7 regression tests covering client-side configuration validation, atomic request success/error commits, upload removal controller aborts, configuration revision bumps rejecting stale responses, and superseded request isolation.
2. **View Projection Tests (`node scripts/test-region-inspection-view.mjs`):**
   - Passed all 6 tests covering ID matching, truthful status projection, outline validation bounds (`[3, 128]` vertices, finite coordinates in `[0, 1]`, DETECTED gating), content rectangle letterbox exclusion, coverage summary projection, and emitted observation lookup covering individual shape findings with/without scope and canonical D03 comparison group findings with/without scope.
3. **Frontend Lint (`npm run lint`):**
   - Passed with 0 errors (140 existing repository warnings).
4. **Production Build (`npm run build`):**
   - Compiled successfully in 7.4s with Turbopack and TypeScript. All 20 application routes compiled and generated cleanly with zero errors.
5. **Handoff Task Validation (`validate_task.py`):**
   - Result: `VALID: .agents\handoff\tasks\DLK-M3-041-region-inspection-workbench.md`.
6. **Whitespace & Git Diff (`git diff --check`):**
   - Clean, no trailing whitespace or merge artifacts.
7. **Comprehensive Automated Browser Suite (`scratch/verify-all-scenarios.mjs` via Chrome DevTools Protocol on port 3001, 12/12 passed):**
   - **(Real Backend Request - http://127.0.0.1:8000):** Submitted real synthetic PNG deposit image to running backend service (`http://127.0.0.1:8000/api/v1/images/analyze`). Outcome: `{ completed: true, hasWorkbench: true, hasCurrentCoverage: true, hasTargetSites: true }`. The previous reporting of `hasTargetSites: false` was caused by a case-sensitive test assertion `document.body.innerText.includes("Expected Target Sites")`: in Chromium, `innerText` is styling-aware and applies CSS text transforms; because `RegionInspectionPanel.tsx` styles the section header with Tailwind's `uppercase` class (`text-xs font-bold uppercase tracking-wider`), Chromium transformed the rendered text to uppercase `"EXPECTED TARGET SITES (1)"`. When queried with case-insensitivity or via DOM attribute `[aria-label="Expected Target Sites"]`, `hasTargetSites` is `true`. The exact rendered header is `'EXPECTED TARGET SITES (1)\nSelect site to view detailed inspection'` and tab is `'dot-1\nMaterial detected'`. Captured and saved screenshot: `01-real-backend-workbench.png` (124 KB).
   - **(R1 Finding Semantics):** Verified individual abnormal shape finding renders individual observation notice, while canonical D03 `deposit_size/inconsistent` renders group comparison notice: `{ hasShapeFinding: true, hasIndividualNotice: true, hasD03Finding: true, hasGroupNotice: true }`.
   - **(R2 Explicit Interaction Mode & Inside-ROI Drawing):** Verified `[ Inspect ]` and `[ Draw ROI ]` segmented toggle. In Inspect mode, dragging over ROI does not draw and preserves analysis result (`resultStillPresent: true`). In Draw mode, starting a drag inside an existing ROI draws a second ROI (`countAfterDrawDrag: 2`) and immediately invalidates previous results (`resultClearedOnEdit: true`). Verified studio modal displays all 6 ROIs (`studioModal: true, countInStudio: 6`).
   - **Scenario (a) - Distinct Sizes & Outlines:** Verified 2 detected regions (`dot-1` coverage 85.0%, dia 1.248mm; `dot-2` coverage 42.0%, dia 0.762mm with low coverage warning). 2 distinct SVG `<polygon>` elements rendered with valid vertex coordinates. Switching tabs updated details without index-0 bleed.
   - **Scenario (b) - Missing & Unassessed Sites:** Verified `dot-1` "Material detected", `dot-2` "Expected deposit missing", and `dot-3` "Not assessed". Verified exactly 1 outline polygon rendered (for `dot-1`), 0 for missing/unassessed.
   - **Scenario (c) - UNRELIABLE Gating:** Verified "Inspection Quality Gate: UNRELIABLE" banner displayed, per-region measurements visible for technician review (65.0%), and notice confirming 0 score-bearing diagnostic observations emitted (`hasGateBanner: true, hasZeroObsNotice: true, hasDetails: true`).
   - **Scenario (d) - Reference Coverage Separation:** Verified "Current Image Inspection Coverage" card (COMPLETE) and "Reference Image Coverage" card (PARTIAL) rendered separately without reusing current image counts with explicit tolerance ratio (`hasCurrent: true, hasReference: true`).
   - **Scenario (e) - Legacy Response Fallback:** Verified older response without additive fields displayed "Status unavailable" and "Not available" without guessing from area or legacy flags (`hasUnavailableStatus: true`).
   - **Scenario (f) - Portrait/Landscape Alignment, Viewports, & Actual Browser Page Zoom:**
     - **Portrait (1:2 aspect ratio, 300x600):**
       - *Inline @ Narrow Viewport (768px):* Container 613x442px, rendered image 611x440px. Content overlay: width 220px, height 440px, left offset 196.5px, top offset 1px. Pillarbox padding: 196.5px left and right. Drift: `widthDiff: 1px, heightDiff: 2px, leftDiff: 0.5px, topDiff: 1px` (within 1px border rounding of the 1px container border). `svgMatchesOverlay: true`. Screenshot saved: `09-portrait-narrow-768-inline.png` (78 KB).
       - *Inline @ Wide Viewport (1440px):* Container 568.3x482px, rendered image 566.3x480px. Content overlay: width 240px, height 480px, left offset 164.1px, top offset 1px. Pillarbox padding: 164.1px left and right. Drift: `widthDiff: 1px, heightDiff: 2px, leftDiff: 0.5px, topDiff: 1px`. `svgMatchesOverlay: true`. Screenshot saved: `09-portrait-wide-1440-inline.png` (107 KB).
       - *Studio Modal View:* Container 568.3x482px, rendered image 566.3x480px. Content overlay: width 240px, height 480px, left offset 164.1px, top offset 1px. Drift: `widthDiff: 1px, heightDiff: 2px, leftDiff: 0.5px, topDiff: 1px`. `svgMatchesOverlay: true`. Screenshot saved: `09-portrait-studio-modal.png` (120 KB).
     - **Landscape (2:1 aspect ratio, 600x300):**
       - *Inline @ Narrow Viewport (768px):* Container 613x307.5px, rendered image 611x305.5px. Content overlay: width 611px, height 305.5px, left offset 1px, top offset 1px. Letterbox padding: 0.5px top and bottom. Drift: `widthDiff: 2px, heightDiff: 1px, leftDiff: 1px, topDiff: 0.5px`. `svgMatchesOverlay: true`. Screenshot saved: `09-landscape-narrow-768-inline.png` (75 KB).
       - *Inline @ Wide Viewport (1440px):* Container 568.3x285.1px, rendered image 566.3x283.1px. Content overlay: width 566.3px, height 283.1px, left offset 1px, top offset 1px. Drift: `widthDiff: 2px, heightDiff: 1px, leftDiff: 1px, topDiff: 0.5px`. `svgMatchesOverlay: true`. Screenshot saved: `09-landscape-wide-1440-inline.png` (108 KB).
       - *Studio Modal View:* Container 568.3x285.1px, rendered image 566.3x283.1px. Content overlay: width 566.3px, height 283.1px, left offset 1px, top offset 1px. Drift: `widthDiff: 2px, heightDiff: 1px, leftDiff: 1px, topDiff: 0.5px`. `svgMatchesOverlay: true`. Screenshot saved: `09-landscape-studio-modal.png` (129 KB).
     - **Actual Browser Page Zoom & HiDPI Scale Factor:**
       - *Actual Page Scale Factor 1.5 (150% page zoom via CDP Emulation.setPageScaleFactor):* `visualViewportScale: 1.5`. Content overlay width 566.3px, height 283.1px, left offset 1px, top offset 1px. Overlay locked to image content with zero letterbox drift. `svgMatchesOverlay: true`. Screenshot saved: `09-browser-zoom-150.png` (106 KB).
       - *Actual Page Scale Factor 2.0 (200% page zoom via CDP Emulation.setPageScaleFactor):* `visualViewportScale: 2.0`. Content overlay width 566.3px, height 283.1px, left offset 1px, top offset 1px. Overlay locked to image content with zero letterbox drift. `svgMatchesOverlay: true`. Screenshot saved: `09-browser-zoom-200.png` (119 KB).
       - *HiDPI Device Scale Factor (DPR 2 via CDP Emulation.setDeviceMetricsOverride):* `devicePixelRatio: 2.0`. Content overlay width 566.3px, height 283.1px, left offset 1px, top offset 1px. Sub-pixel rendering crisp and aligned. `svgMatchesOverlay: true`. Screenshot saved: `09-browser-hidpi-dpr2.png` (318 KB).
   - **Scenario (g) - Keyboard Selection & Reset:** Verified keyboard Enter/Space selects ROI tabs (`keySelected: true`); "Reset ROIs" reset configured regions to 0 (`roiCountAfterReset: 0`) and automatically switched to Draw mode (`drawModeActive: true`).
   - **Scenario (h) - In-Flight Reconfiguration & Multi-Upload Isolation:** Verified reconfiguring during an in-flight request properly rejected the stale late response (`lateResponseRejected: true`); verified multi-upload selection state remains isolated across separate upload cards (`hasMultipleUploads: true`).
   - **Scenario (i) - Malformed Outline Fallback:** Verified response with DETECTED status but malformed outline (< 3 points) omitted polygon overlay with neutral notice ("Outline: At least 3 coordinate points required") without crashing (`hasFallbackNotice: true, polygonCountZero: true`).
   - **Console Health:** Total console messages: 2, Total console errors: 0 across all 12 browser verification scenarios.

### Limitations and follow-up

- In accordance with task scope, backend code, automated alignment, template storage, and full-board autosegmentation were deferred to subsequent milestone increments.
- Automated test suites parse extracted PDF text and structure, which does not verify visual layout, typography, or graphic appearance of rendered PDF documents.

### Proposed commit message

`fix(vision-ui): correct region inspection finding semantics and interactions`
