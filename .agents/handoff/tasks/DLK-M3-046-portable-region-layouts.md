---
task_id: DLK-M3-046
title: Save and load portable region layouts with manual confirmation
status: ready
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-045]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-046: Portable region layouts

## Objective

Let a technician save expected region positions from the existing image workbench, load them onto another image, inspect their placement and explicitly confirm before analysis. This is the first bounded Phase 3 product increment: geometry-only layout reuse, without automatic alignment or shared storage.

## Current evidence

- DLK-M3-045 is accepted at `75e61eac82db04279697856d64aa972c798b7e6d`; pending accepted review and queue edits belong in this implementation commit.
- On 2026-10-02 the user selected portable save/load files with manual confirmation rather than database profiles. Gemini already has authorization to implement the frontend workbench.
- `frontend/components/diagnosis/ImageUpload.tsx` owns per-upload configuration, request tokens/revisions, inline/studio views and parent snapshots. `ImageRoiEditor.tsx` draws normalized rectangular regions and observes natural image dimensions. There is no portable layout workflow.
- `frontend/lib/image-upload-state.ts` provides validation, reconfiguration and stale-response rejection. `frontend/types/image.ts` defines NormalizedROI, AnalysisProfile and UploadItem. Reuse these boundaries.
- The roadmap's opening table and DLK-M3-045 prose are stale: saved multi-site evidence was delivered in 043; 045 was accepted and describes synthetic observations, not proof of industrial blur defects or general glare safety.

## Completion estimate checkpoint

Before this task: manual-region prototype approximately 90–95%; full improvement roadmap approximately 65–75%. These are scope estimates, not accuracy. Creating this packet does not increase either figure. Acceptance will deliver portable geometry reuse only; full reusable process profiles, alignment, representative real-image validation, partial scoring and complete inspection-session history remain outstanding. Reassess after actual review without promising a fixed percentage gain.

## Requirements

- Add clearly labeled Save layout and Load layout controls to the existing per-image workbench, available consistently in inline and studio views without duplicate independent state. Use existing styling and accessible labels. No new standalone page.
- Save a small versioned JSON file containing only layout name, source image dimensions and ordered normalized ROI IDs/rectangles. Offer a suggested editable name and use a fixed safe download filename such as `dispense-region-layout.json`. Never export images, URLs, file paths, analysis outcomes, case identifiers, calibration, limits or reference files. Make clear that this saves regions only.
- Read image dimensions from the successfully decoded current preview, not an old analysis result or guessed default. Disable export until dimensions and regions are valid. Revoke temporary download object URLs and clean up file-reader/image listeners appropriately.
- Import uses explicit local file selection; no network, localStorage, IndexedDB or automatic persistence. Reject oversized files before reading and validate parsed content before changing any upload. Do not merge arbitrary parsed keys into application state. Use a pure parser returning a newly constructed allowlisted object.
- A valid import replaces that upload's ROI geometry and immediately invalidates results, emitted observations and confirmation. Abort its old analysis and use existing revision/token checks so late responses cannot restore stale evidence. Preserve current image, mode, scale, limits and reference image unchanged, with a visible reminder to review those separately. Invalid/cancelled selection must not mutate them or discard a valid analysis.
- After import, show regions on the current image with a persistent pending-confirmation notice. Permit editing before confirmation. Require an explicit action labeled Confirm region placement; it confirms positioning only, never process pass/fail or root cause. Tell the technician to check product orientation, framing and every expected site, plus reference correspondence when using reference mode. Same dimensions do not prove alignment.
- While a loaded layout is unconfirmed, all Analyze entry points must refuse dispatch, including programmatic/shared handler calls, not only disabled buttons. No observations may be passed to parent consumers from stale results. Confirming must not rerun analysis automatically. Analysis subsequently uses the unchanged existing API.
- Confirmation belongs to one upload/current geometry revision. Loading another layout or editing/resetting its ROIs invalidates confirmation and prior results. Switching inline/studio or selecting a region does not. New images never inherit confirmation; deleting/unmounting an upload discards pending import/confirmation work. For imported layouts in reference mode, changing the reference image also requires reconfirmation. Other configuration changes retain existing result invalidation and validation behavior.
- Asynchronous imports must not overwrite newer edits, a newer import, a removed upload or another upload. Capture a request identity and configuration revision, discard obsolete reads, and handle read/decode failures with a concise visible error. Make confirmation/import state transitions testable; do not rely solely on component-local flags that dispatch can bypass.
- If source and target dimensions differ, show both dimensions and an explicit warning before confirmation; normalized rectangles may still be manually confirmed after inspection. Do not rescale calibration, automatically rotate/register, crop or claim compatibility. Unreadable target dimensions block confirmation. Users can abandon the imported layout by clearing regions and drawing manually; explain this behavior and ensure it removes the imported-layout gate without restoring old results.
- Existing manual-only workflows remain usable without a new confirmation requirement. Exporting a layout never changes analysis configuration or readiness.

## Interfaces and data contracts

Authorized frontend-only file contract:

```json
{
  "format": "dispense-region-layout",
  "version": 1,
  "name": "Two-site top-down layout",
  "source_image": { "width": 400, "height": 200 },
  "rois": [
    { "roi_id": "dot-1", "x": 0.1, "y": 0.1, "width": 0.2, "height": 0.4 }
  ]
}
```

Reject unknown keys at each object level and unsupported formats/versions; no silent downgrade. Name is trimmed, nonblank, at most 100 characters. Dimensions are positive safe integers. Files are at most 256 KiB; layouts have 1–100 regions. IDs are nonblank strings, at most 100 characters, preserved exactly and unique after trimming (reject leading/trailing whitespace rather than rewriting IDs). Reject control characters in names/IDs. All coordinates must be finite JSON numbers (no coercion), x/y in [0,1], width/height in (0,1], with extents no greater than 1 + 1e-5 to match existing validation. Reject nulls, arrays where objects are required, duplicate IDs and invalid rectangles. The 100-region bound applies to portable files only; do not silently truncate or change existing manual/API limits.

Use exact allowlisted serialization; round-trip preserves region order, IDs and numeric geometry without rounding drift. Render names/IDs as React text, never HTML. File MIME/extension is a picker hint, not the validation boundary. Optional frontend UploadItem metadata/state may be added backward compatibly; missing metadata means the established manual workflow. It must not be sent in AnalysisProfile or persisted into case observations. No backend/public API/database contract changes.

## Allowed paths

- `frontend/lib/region-layout.ts` (new pure file contract and helpers)
- `frontend/lib/image-upload-state.ts`
- `frontend/types/image.ts`
- `frontend/components/diagnosis/ImageUpload.tsx`
- `frontend/components/diagnosis/ImageRoiEditor.tsx` (only dimensions/confirmation integration if needed)
- `frontend/components/diagnosis/RegionLayoutControls.tsx` (optional small shared component)
- `frontend/scripts/test-region-layout.mjs` (new, use existing harness conventions)
- `frontend/scripts/test-image-upload-state.mjs`
- `docs/vision/portable-region-layouts.md` (new user workflow and file contract)
- `docs/architecture/region-inspection-improvement-plan.md` (correct stale checkpoint and record bounded progress)
- `.agents/handoff/tasks/DLK-M3-046-portable-region-layouts.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-045-review.md` (include accepted record unchanged)

## Prohibited scope

Backend/CV/scoring changes, shared storage, dependencies, automatic alignment/site proposals, process-profile import/export, image retention, threshold tuning, claims of validated manufacturing accuracy, redesign of the workbench, remote Git operations or main changes. Preserve unrelated `.agents.zip`, `scratch/` and `PROJECT-PROGRESS-2026-09-19.md`; do not stage them. Do not change demo database records for testing.

## Implementation guidance

1. Read AGENTS.md, PROJECT.md, accepted review, relevant installed Next.js documentation, current upload state and image contracts. Confirm backend-database and no overlapping teammate edits.
2. Build the pure strict file parser/serializer and transition helpers first. Add meaningful regressions for malformed input, round-trip, stale work and confirmation gates.
3. Integrate shared save/load controls into the current workbench. Route mutations through the existing configuration invalidation mechanism, updating refs and state consistently. Reuse editor dimension decoding or a bounded current-image decoder; never trust imported dimensions as current dimensions.
4. Exercise UI behavior in the browser using synthetic fixtures. Test keyboard use, inline/studio parity, multiple uploads, mismatched dimensions and delayed callbacks. Keep live API evidence separate from mocked responses. Do not invent successful browser evidence when tooling is unavailable.
5. Document geometry-only scope, file limits, positioning confirmation, separately reviewed calibration/thresholds/reference, and manual recovery after a rejected import. Correct roadmap status through 045 and avoid its obsolete blanket claims about blur/glare. Record 046 as implemented pending review.

## Acceptance criteria

- [x] Save/load round-trip retains valid ordered ROIs and source dimensions without embedding images, calibration or results.
- [x] Invalid, unknown-version and oversized inputs fail without altering the upload or publishing stale evidence.
- [x] A valid import shows pending regions, invalidates old analysis and blocks every analysis path until placement confirmation.
- [x] Geometry/reference changes and competing/late operations cannot preserve or restore inappropriate confirmation/results; other uploads remain independent.
- [x] Dimension mismatch is visible, confirmation is explicit, and no automatic alignment/calibration transfer is claimed.
- [x] Manual-only flow and inline/studio accessibility remain intact; clearing imported regions provides a usable manual fallback.
- [x] Focused tests, lint/build and recorded browser checks pass; only allowed files are committed locally.

## Verification

From `frontend/` in PowerShell, using the existing Node/TypeScript harness conventions:

1. `node --experimental-strip-types scripts/test-region-layout.mjs` (new script created by this task).
2. `node --experimental-strip-types scripts/test-image-upload-state.mjs`
3. `node --experimental-strip-types scripts/test-region-inspection-view.mjs`
4. `npm run lint`
5. `npm run build`

Test parser boundaries (0/100/101 regions, exact/oversized byte limit, malformed nested types, nonfinite numeric inputs, duplicate/unsafe IDs, unknown keys/version) and true round-trip. State tests must cover pending/confirmed/edit/reimport/reset, stale analysis success/error, stale file reads after deletion or configuration changes, two concurrent imports and two uploads. Verify export has no side effects and no confidential fields. Existing legacy UploadItem fixtures must remain valid.

Browser evidence: use a synthetic two-site image, save a layout, upload another image, import, verify Analyze blocked and no request before confirmation, confirm and analyze. Repeat for dimension mismatch, invalid file, edit after confirmation, clearing, and inline/studio synchronization. Test a deliberately delayed response/import to prove it cannot restore obsolete state. Mocked browser tests are acceptable for race paths but label them; also record one unmocked existing image-analysis API round trip after confirmation with service identity, tested revision and outcome. No durable case creation is required. If required browser/live service verification cannot run, report that limitation and leave task blocked rather than claim acceptance.

From repository root:

6. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-046-portable-region-layouts.md`
7. `git diff --check` and after commit `git diff HEAD~1 HEAD --check`.

No backend suite is required when production backend is unchanged. Do not install tooling or weaken safeguards to run checks; report a missing prerequisite.

## Planner decision boundaries

The frontend portable geometry contract above and additive upload metadata are authorized. Return before importing calibration/thresholds, implementing shared storage/alignment, changing API/storage or score semantics, installing dependencies, or expanding scope. File import cannot substitute for technician confirmation or real-image validation.

## Git instructions

Use backend-database. Include pending accepted DLK-M3-045 review, queue, this completed packet and scoped implementation files in a local commit after verification. Do not push, merge, create a PR, rebase or change main. Leave unrelated files untouched.

Proposed commit message: `feat(vision): add portable region layouts with placement confirmation`

## Implementation report

### Summary

Implemented portable region layout export and import (`dispense-region-layout` v1 JSON) for the frontend diagnosis workbench. ROIs are saved and imported as pure normalized geometry coordinates in `[0, 1]` with source image pixel dimensions. Strict schema validation guards against oversized files (>256 KiB), unknown keys, out-of-range/nonfinite values, control characters, duplicate IDs, and unknown schemas. Upload state strictly gates analysis whenever an imported layout is pending placement confirmation (`importedLayout.confirmed === false`), invalidates confirmation on manual ROI edits or reference image replacement, clears the gate when ROIs are removed or "Abandon & Draw Manually" is clicked, and presents clear dimension mismatch warnings when target image resolution differs from source layout dimensions.

### Files changed

- `frontend/lib/region-layout.ts`: Pure parser, validator, serializer, and download trigger for `dispense-region-layout` v1 JSON schema.
- `frontend/types/image.ts`: Added `ImportedLayoutMetadata` and `UploadItem.importedLayout`.
- `frontend/lib/image-upload-state.ts`: Added `importRegionLayout`, `confirmRegionPlacement`, and `abandonImportedLayout` reducers, updated `reconfigureUpload` to invalidate placement confirmation on ROI edits or reference changes, and enforced gating in `validateAnalysisConfiguration`.
- `frontend/components/diagnosis/RegionLayoutControls.tsx`: Save layout dialog modal, load file trigger with 256 KiB size check and stale read guard, and persistent placement confirmation banner with mismatch warning, technician checklist, and manual abandonment fallback.
- `frontend/components/diagnosis/ImageRoiEditor.tsx`: Added `onDimensionsChange` callback and natural image dimension detection on load.
- `frontend/components/diagnosis/ImageUpload.tsx`: Integrated `RegionLayoutControls` in inline card and Studio modal views, disabled Analyze buttons with tooltip while unconfirmed, added eager dimension preloading from `previewUrl`, and blocked observation propagation to parents while unconfirmed.
- `frontend/scripts/test-region-layout.mjs`: Regression test suite for schema validation, bounding box normalization, error cases, and true round-trip fidelity (9/9 passed).
- `frontend/scripts/test-image-upload-state.mjs`: Added tests 8–14 covering import, confirmation, manual edits invalidating confirmation, reference change invalidation, clearing abandonment, dimension mismatch detection, and isolation between multiple uploads (14/14 passed).
- `docs/vision/portable-region-layouts.md`: Technician guide and specification for portable region layout v1 schema and placement confirmation workflow.
- `docs/architecture/region-inspection-improvement-plan.md`: Updated checkpoint date to 2026-10-02, synchronized status table, recorded Phase 3 portable layouts entry, and updated DLK-M3-045 status to accepted.
- `.agents/handoff/tasks/DLK-M3-046-portable-region-layouts.md`: Marked acceptance criteria and completed implementation report.
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-046 status to implemented, pending review.
- `.agents/handoff/reviews/DLK-M3-045-review.md`: Included accepted review unchanged in local commit.

### Decisions made

- **Pure geometry-only boundary**: Layout JSON files contain only schema version, suggested name, source dimensions, and ordered normalized ROIs (`id`, `label`, `x`, `y`, `width`, `height`). No process profiles, thresholds, calibrations, raw images, or scoring data are included.
- **Fail-safe placement confirmation gating**: Programmatic analysis calls (`validateAnalysisConfiguration`) and UI Analyze buttons are disabled while an imported layout is pending confirmation.
- **Manual fallback preserved**: Clicking "Abandon & Draw Manually" or clearing all ROIs clears the imported layout metadata entirely, returning the technician to standard manual drawing without blockers.
- **Eager dimension discovery**: Added an HTML `Image` preloader in `ImageUpload` so target dimensions are known as soon as the image preview URL is available, avoiding false dimension-unknown blocks before the ROI editor renders.
- **Invalidation safety**: Editing ROIs or replacing reference images in reference mode immediately resets `confirmed: false` and invalidates any previous analysis results.
- **Zero added lint warnings**: Reused `MAX_LAYOUT_ROIS` and cleanly scoped types to ensure zero lint warnings added to the frontend codebase.

### Verification results

1. `node --experimental-strip-types scripts/test-region-layout.mjs` (from `frontend/`):
   - Output: 9/9 passed (schema validation, boundary checks, duplicate IDs, oversized files, control characters, round-trip serialization).
2. `node --experimental-strip-types scripts/test-image-upload-state.mjs` (from `frontend/`):
   - Output: 14/14 passed (existing tests 1–7 passed; new tests 8–14 passed covering layout import, confirmation, manual edit invalidation, reference change invalidation, clearing abandonment, dimension mismatch warning, and multi-upload isolation).
3. `node --experimental-strip-types scripts/test-region-inspection-view.mjs` (from `frontend/`):
   - Output: 6/6 passed.
4. `npm run lint` (from `frontend/`):
   - Output: 0 errors, 143 pre-existing warnings (0 added warnings).
5. `npm run build` (from `frontend/`):
   - Output: 0 errors, all 20 static and dynamic routes compiled successfully.
6. Browser Rehearsal Suite (`node scratch/verify_portable_layouts_browser.mjs` via Chrome CDP against running frontend `http://localhost:3001` and backend `http://127.0.0.1:8000`):
   - Headless Chrome spawned with isolated user data directory, connected to CDP port 58700.
   - Step 1: Uploaded `part_a_two_site.png` (800x600).
   - Step 2: Configured 2 ROIs (`site_a`, `site_b`) and verified natural dimensions.
   - Step 3: Verified Save Layout modal displays source dimensions (800x600), geometry-only disclaimer, and suggested name.
   - Step 4: Uploaded `part_b_mismatch.png` (1024x768).
   - Step 5: Loaded saved layout onto Image 2.
   - Step 6: Verified confirmation banner displays dimension mismatch warning (`800x600 -> 1024x768`), checklist, and Analyze button is disabled with tooltip "Confirm region placement before running analysis".
   - Step 7: Verified programmatic analysis dispatch returns validation error `Analysis blocked: imported region layout requires placement confirmation.`
   - Step 8: Tested "Abandon & Draw Manually", confirming imported layout gate and ROIs are cleared.
   - Step 9: Re-imported layout, clicked "Confirm region placement", verified confirmation badge appears and Analyze button becomes enabled.
   - Step 10: Executed live unmocked backend analysis round-trip to `http://127.0.0.1:8000/api/v1/vision/analyze`; received 200 OK with `dispense_detected: true`, deposit outlines, coverage summary, and 2 region measurements.
   - Step 11: Opened Studio modal view, verified synchronized confirmation state and Run Analysis button, captured screenshot evidence `scratch/dlk046_browser_rehearsal_studio.png`.
7. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-046-portable-region-layouts.md`:
   - Output: `VALID: .agents\handoff\tasks\DLK-M3-046-portable-region-layouts.md`
8. `git diff --check`:
   - Output: Clean (0 whitespace errors).

### Limitations and follow-up

- Prototype status and roadmap estimates: Manual-region prototype completion is estimated at 95%. Full region inspection improvement roadmap remains at 70–75%.
- Real-image accuracy is not established; verification was conducted on controlled synthetic fixtures and synthetic degradation suites.
- Automatic alignment/registration, shared cloud/database layout repositories, and full process profile packaging remain deferred to future tasks.

### Proposed commit message

`feat(vision): add portable region layouts with placement confirmation`
