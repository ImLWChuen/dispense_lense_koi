---
task_id: DLK-M3-043
title: Display persisted multi-site image evidence on saved cases
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-042]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-043: Saved-case multi-site evidence

## Objective

Let technicians inspect every recorded affected region and its supplied limits after saving or reloading a case. Close the Phase 4 saved-case presentation gap using existing persisted observations, without introducing image retention, new inspection sessions or diagnostic behavior.

## Current evidence

- DLK-M3-042 accepted at a9803d01db253437c564ddea2dac743995957a6a. Pending planner review/queue edits must be included unchanged except the new task's lifecycle updates.
- frontend/components/diagnosis/ImageAnalysis.tsx filters IMAGE observations but renders only legacy top-level measurements. Its footer also describes geometric metadata too broadly.
- backend/app/services/vision/defect_classifier.py creates affected_roi_ids, region_evidence_scope, applied_limits and region_evidence entries containing roi_id, current_measurements and optional reference_measurements. These are scalar snapshots, not saved images or outlines.
- Existing JSON/PDF reports expose this evidence. DLK-M3-042 proves two distinct sites survive browser intake and persistence; frontend saved-case display is the remaining bounded integration gap.
- User authorized Gemini frontend work for region inspection. This packet extends that work to the saved-case evidence component only. Profiles/alignment and partial evidence remain separate decisions.

## Requirements

- Render each IMAGE observation once, preserving its value, provenance and existing context. Show all recorded affected IDs and per-region snapshots in stable order, with readable selectable or expandable site details. Keep the existing visual style and keyboard-accessible controls.
- Show current and reference measurements separately, explicitly labeling absent reference data as not recorded rather than zero. Include inspection status, area, coverage/overflow, pixel diameter, physical diameter only when recorded and finite, shape/void metrics and segmentation quality where available. Use accurate units; quality is not diagnostic probability or Evidence Support.
- Display supplied applied_limits using a known-key allowlist and finite numeric values. Never invent absent limits, mm-per-pixel, status, pass/fail, or a fresh classification. Measurements alone are not process acceptance or root-cause confirmation.
- Honor explicit individual_regions/comparison_group scope. Comparison-group observations describe the group rather than asserting every participant independently failed. Unknown scope stays unknown; any legacy D03 fallback must match the existing canonical deposit_size/inconsistent contract, not every shape observation.
- Treat metadata as untrusted runtime data. Safely narrow arrays, objects, IDs, finite numbers, booleans and enum statuses. Malformed entries must not crash the page or be rendered as raw objects. Preserve usable entries and show unavailable/unknown for missing fields. Avoid duplicate React keys even with repeated/missing IDs; do not silently merge conflicting entries or fabricate identifiers as recorded evidence.
- Distinguish an affected ID with no usable snapshot from a measured site. Do not attach first-site legacy measurements to every affected site. Legacy observations without region_evidence retain a clearly labeled legacy summary. Present but malformed region_evidence must not masquerade as a complete multi-site record.
- Bound initially visible long lists using accessible expansion/pagination without silently losing entries. Wrap long IDs/text and keep the layout usable on mobile. No new dependency.
- Explain that this is recorded diagnostic evidence for affected sites, not a complete inspection session or list of all expected sites. Do not infer overall coverage or overall pass from the saved subset. No-image-evidence state must remain neutral.
- Correct retention copy: raw images and outlines are unavailable after saving; persisted observations retain IDs, supplied limits and scalar measurements. No image reconstruction or outline viewer on saved cases.

## Interfaces and data contracts

Read existing CaseObservationResponse.metadata only. No API/schema/storage changes, mutations, recomputation or scoring effects. A small pure frontend projection helper may normalize unknown metadata into a safe view model. Do not force persisted snapshots into live RoiMeasurement contracts that require absent image geometry/warnings. Preserve legacy cases and existing observation ordering.

## Allowed paths

- frontend/components/diagnosis/ImageAnalysis.tsx
- frontend/components/diagnosis/SavedRegionEvidence.tsx (optional new presentation component)
- frontend/lib/saved-region-evidence.ts (new pure helper)
- frontend/scripts/test-saved-region-evidence.mjs (new tests using existing script conventions)
- docs/demo/region-inspection-acceptance.md
- docs/architecture/region-inspection-improvement-plan.md (progress wording only)
- .agents/handoff/tasks/DLK-M3-043-saved-case-region-evidence.md
- .agents/handoff/QUEUE.md
- .agents/handoff/reviews/DLK-M3-042-review.md (include accepted record unchanged)

## Prohibited scope

Backend/API/database changes, image retention, saved inspection-session schema, new dependencies, upload-workbench redesign, profiles/alignment, automatic site detection, partial score-bearing evidence, new scores/thresholds, broad frontend refactoring, remote Git operations and main changes. Preserve unrelated .agents.zip and PROJECT-PROGRESS-2026-09-19.md. Never reset existing data or commit generated screenshots, PDFs or secrets.

## Implementation guidance

1. Read applicable AGENTS.md, PROJECT.md, accepted review, installed Next.js guidance and existing projection-test conventions. Inspect actual persisted metadata and reporting guards before coding.
2. Create a defensive projection helper and meaningful regression fixtures for two distinct current sites, reference pairs, group scope, legacy data, absent fields, malformed values and repeated IDs. Keep stored evidence unmodified.
3. Integrate a readable saved-case view. Retain useful legacy metadata as explicitly legacy/first-affected-site context, never as a substitute for all regional snapshots.
4. Verify in the browser using actual saved-case API data from the accepted rehearsal or a newly labeled synthetic case. Inspect both sites, navigate away/reload, verify unchanged measurements and limits. Check keyboard operation, narrow viewport and console. Use mocked fixtures only for malformed/legacy boundaries and label them as such.
5. Update the guide and roadmap precisely; Phase 4 still lacks full inspection-session history. Complete report, validate packet, commit locally.

## Acceptance criteria

- [x] One deduplicated image observation shows both recorded sites with their distinct measurements after reload.
- [x] Current/reference data and supplied limits are separately and truthfully displayed; absent calibration never becomes a physical measurement.
- [x] Group scope, unknown status, legacy records, missing snapshots and malformed metadata remain understandable without crashes or duplicate-key warnings.
- [x] All entries are reachable with keyboard-accessible controls; narrow layout handles long content.
- [x] Saved subset is not described as complete inspection coverage, process pass or root-cause confirmation; no image/outline retention claim.
- [x] Focused regressions, lint, build and real saved-case browser verification recorded with actual results and limitations.
- [x] Only allowed changes committed locally; existing records preserved.

## Verification

From repository root in PowerShell:

1. `node frontend/scripts/test-saved-region-evidence.mjs` (create following existing script conventions).
2. `node frontend/scripts/test-region-inspection-view.mjs`
3. `node frontend/scripts/test-image-upload-state.mjs`
4. From frontend/: `npm run lint` and `npm run build`. Record pre-existing warnings separately; no new task-related errors/warnings.
5. Real browser saved-case check on port 3001 with actual backend on 8000: both sites, limits, reload, keyboard, narrow viewport and console. Report case ID, service identity, tested commit/base and local artifact paths. Do not mutate existing case data simply to demonstrate presentation. Reference/legacy/malformed cases may use explicitly labeled browser mocks; no mock presented as live API evidence.
6. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-043-saved-case-region-evidence.md`
7. `git diff --check`

Backend suites need not be rerun for this frontend-only task. No database reset or environment replacement. If browser verification is blocked, record the cause and do not claim completion.

## Planner decision boundaries

Return to planner before backend, schema, retention, score, dependency or broader ownership changes. This task authorizes saved-case presentation only; absent stored information is shown as unavailable, not solved through new persistence.

## Git instructions

Work on backend-database. Include completed task, queue and pending accepted DLK-M3-042 review with scoped implementation in one local commit after verification. Do not push, merge, rebase, create a PR or change main.

Proposed commit message: `feat(vision-ui): display saved multi-site inspection evidence`

## Implementation report

### Summary

Delivered saved-case multi-site image evidence presentation on `/diagnosis/[id]/analysis` using the new `SavedRegionEvidence.tsx` component and defensive projection helper `frontend/lib/saved-region-evidence.ts`. Closed the Phase 4 saved-case display gap by projecting persisted `metadata.region_evidence`, `affected_roi_ids`, `applied_limits`, and `region_evidence_scope` into accessible site selection tabs and 15-parameter scalar evidence snapshots. Applied limits are strictly allowlisted against 21 known configuration keys and formatted with units. Current and reference measurements are rendered separately, with unassessed or omitted reference data explicitly labeled as "Not recorded" rather than zero. Scope handling differentiates `individual_regions` from `comparison_group` (and canonical D03 `deposit_size/inconsistent` fallback). Untrusted runtime metadata is defensively narrowed to prevent crashes, duplicate React keys, or raw object rendering. Legacy observations lacking `region_evidence` gracefully fall back to a clearly labeled single-site summary card. Updated the data retention footer note in `ImageAnalysis.tsx` to truthfully explain that raw images and full polygon outlines are discarded after analysis, while scalar measurements, target ROI IDs, and threshold limit snapshots are preserved in durable storage.

### Files changed

- `frontend/lib/saved-region-evidence.ts`: New pure projection helper module. Implements defensive narrowing of runtime metadata, allowlisted applied limits (`KNOWN_LIMIT_KEYS`), scope resolution, unmeasured affected ID detection, 15-parameter scalar measurement parsing, formatting helpers, and legacy observation fallback.
- `frontend/components/diagnosis/SavedRegionEvidence.tsx`: New accessible React component for displaying saved multi-site region evidence. Features observation header with scope badge and explanation note, summary cards for recorded affected sites and applied limits, selectable site tabs (`role="tablist"` / `role="tab"`) with inspection status badges (`DETECTED`, `MISSING`, `UNASSESSED`, `UNKNOWN`), keyboard navigation (`ArrowLeft`, `ArrowRight`, `Home`, `End`), 4-metric primary grid, secondary geometric morphology table, separate reference measurements container, and legacy summary fallback.
- `frontend/components/diagnosis/ImageAnalysis.tsx`: Updated to filter `IMAGE` observations, project each observation via `projectSavedRegionEvidence`, render `<SavedRegionEvidence>`, maintain neutral empty state when no image observations exist, and update footer retention copy.
- `frontend/scripts/test-saved-region-evidence.mjs`: New standalone regression test suite verifying 7 distinct areas: two distinct sites with stable order and unique keys, separate reference measurements, scope handling with canonical D03 fallback, legacy observation fallback, untrusted metadata narrowing, unmeasured affected IDs, and formatting helpers.
- `docs/demo/region-inspection-acceptance.md`: Updated Step 5, Section 4 (Readiness Matrix), and Section 5 (Limitations) to reflect delivered saved-case multi-site display capability.
- `docs/architecture/region-inspection-improvement-plan.md`: Added DLK-M3-043 implemented status to Phase 4 roadmap row.
- `.agents/handoff/QUEUE.md`: Updated task lifecycle status to implemented.
- `.agents/handoff/tasks/DLK-M3-043-saved-case-region-evidence.md`: Completed implementation report and acceptance checklist.

### Decisions made

- **Separate Reference Measurements Section:** Reference measurements are never merged with current measurements. When reference data is omitted (single-image mode), a dedicated neutral message ("Not recorded (single-image inspection or unmatched reference site)") is displayed instead of fabricating zero values.
- **Strict Allowlist for Applied Limits:** Defined `KNOWN_LIMIT_KEYS` (21 keys covering coverage, area, diameter, circularity, aspect ratio, solidity, voids, and tolerance) with user-friendly labels and metric-specific formatters. Unknown keys or raw nested objects are safely ignored.
- **Unique React Keys for Corrupt/Duplicate IDs:** Persisted snapshots generate keys combining observation ID, array index, and sanitized ROI ID (`${obsId}-snap-${idx}-${roiIdStr}`) to eliminate duplicate-key console warnings if duplicate or missing IDs occur in metadata.
- **Unmeasured Affected IDs vs Snapshots:** Affected ROI IDs lacking matching snapshots in `region_evidence` are clearly listed as unmeasured affected sites with explanatory context, rather than attaching unrelated measurements to them.
- **Truthful Data Retention Copy:** Footer updated to clarify that raw image uploads and polygon outlines are discarded after analysis, while quantitative scalar defect measurements, target ROI identifiers, and threshold limit snapshots are stored in durable PostgreSQL records.

### Verification results

1. **Saved Region Evidence Unit Test Suite:**
   `node frontend/scripts/test-saved-region-evidence.mjs`
   - Test 1 Passed: Two distinct sites projected with correct limits, measurements, and unique keys.
   - Test 2 Passed: Reference measurements projected separately from current measurements.
   - Test 3 Passed: Scope handled accurately with canonical D03 fallback and shape protection.
   - Test 4 Passed: Legacy observation without region_evidence provides clean first-site summary.
   - Test 5 Passed: Malformed metadata safely narrowed without exceptions or duplicate keys.
   - Test 6 Passed: Affected IDs without snapshots identified as unmeasured.
   - Test 7 Passed: Formatting helpers format numbers, percentages, physical units, and missing states.
   - Outcome: **All 7 tests passed successfully**.

2. **Frontend View Model & State Regressions:**
   - `node frontend/scripts/test-region-inspection-view.mjs`: **All 6 tests passed successfully**.
   - `node frontend/scripts/test-image-upload-state.mjs`: **All 7 tests passed successfully**.

3. **Frontend Lint & Build:**
   - `npm run lint` from `frontend/`: Exited code 0 (144 pre-existing warnings in unrelated legacy files, 0 new errors or warnings).
   - `npm run build` from `frontend/`: Compiled successfully in 6.4s; TypeScript finished with 0 errors; all 18 static and dynamic routes generated, including `/diagnosis/[id]/analysis`.

4. **Real Browser CDP Rehearsal on Live Services:**
   - Services: Backend on `http://127.0.0.1:8000` (`dispense-lens-api` v0.1.0), Frontend on `http://localhost:3001` (`DispenseIQ`), PostgreSQL on port 5432.
   - Target Case: `e1d8db2d-fdce-4edf-974c-97ce671f0792` (accepted DLK-M3-042 rehearsal case with two affected sites).
   - Analysis Page: `http://localhost:3001/diagnosis/e1d8db2d-fdce-4edf-974c-97ce671f0792/analysis`.
   - Observation Header: Title `deposit presence`, badge `missing`, Scope badge `Individual Regions`, Revision badge `Rev 1`. Scope explanation: `Individual region defect findings: each listed region was evaluated and independently triggered defect criteria.`
   - Summary Cards: Recorded Affected Sites: `dot-1`, `dot-2`. Applied Limits Snapshot: `0.75`, `1.35`, `0`, `0.45`, `0.2`, `0.1`, `0.05`.
   - Rendered Site Tabs: `saved-tab-dot-1` (`dot-1 DETECTED`, selected), `saved-tab-dot-2` (`dot-2 DETECTED`).
   - Active Tab 0 (`dot-1`): Coverage `0.9%`, Overflow `0.0%`, Equiv Diam `20.0 px`, Physical Diam `0.399 mm`, Deposit Area `313 px² / 35328 px²`, Circularity `100%`, Reference: `Not recorded (single-image inspection or unmatched reference site)`.
   - Active Tab 1 (`dot-2`): Clicking `dot-2` updated active panel to `Site: dot-2 DETECTED`. Coverage `2.0%`, Overflow `0.0%`, Equiv Diam `30.0 px`, Physical Diam `0.599 mm`, Deposit Area `705 px² / 35328 px²`, Circularity `97%`, Reference: `Not recorded (single-image inspection or unmatched reference site)`.
   - Keyboard Navigation: `ArrowLeft` from `dot-2` tab immediately returned focus and selection to `dot-1`.
   - Mobile Viewport (375x812): Card container adapted to 259px width with cleanly wrapped tabs and responsive table.
   - Retention Footer Note: Confirmed exact text `Raw image files and polygon outlines are not retained in durable storage. Visual evidence is preserved as quantitative scalar defect measurements, target ROI identifiers, and threshold limit snapshots.`
   - Captured Screenshots:
     - `04-saved-case-multi-site-evidence.png` (189 KB, full page screenshot)
     - `04-saved-case-card-detail.png` (focused card header screenshot)
     - `04-saved-case-tabs-detail.png` (tabs and active snapshot metrics screenshot)

5. **Task Validation & Git Hygiene:**
   - `validate_task.py`: VALID.
   - `git diff --check`: 0 errors / 0 trailing whitespace issues.

### Limitations and follow-up

1. **Transient Outlines & No Image Retention:**
   Raw image uploads and polygon contour coordinates (`deposit_outline_normalized`) are transient analysis-response data and are not saved in PostgreSQL cases. Saved cases display scalar measurements, target ROI IDs, and threshold snapshots; visual image replay or outline overlay is intentionally unavailable on saved cases.
2. **Recorded Diagnostic Evidence Scope:**
   Saved-case region evidence represents the affected sites evaluated during diagnostic case creation. It does not represent a persistent interactive inspection session or a historical log of all camera frames.
3. **No Automatic Substrate Alignment:**
   Reference comparison in saved cases relies on the technician having inspected corresponding sites during intake; no automatic optical alignment or fiducial transformation is performed.

### Proposed commit message

`feat(vision-ui): display saved multi-site inspection evidence`

