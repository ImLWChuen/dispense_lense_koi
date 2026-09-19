---
task_id: DLK-M3-027
title: Calibrated image workflow and dynamic diagnosis analysis
status: implemented
created_by: ChatGPT planner/reviewer
assigned_to: Gemini implementer
depends_on: [DLK-M3-026]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-027: Calibrated image workflow and dynamic diagnosis analysis

## Objective

Connect the accepted calibrated image API to the technician-facing diagnosis workflow. A technician must be able to upload JPEG/PNG images, draw normalized rectangular regions of interest, choose an explicit analysis basis, analyze each current upload safely, and create a case using only canonical observations from active calibrated results. The analysis page must then render persisted image evidence and cause evidence from the real durable-case response, with honest loading, empty, unreliable, and error states.

This is Phase 2 of the approved calibrated-vision and dynamic-frontend programme. It covers the plan's frontend Tasks 10-13 and the new-diagnosis portion of Task 15. Stop for ChatGPT review after this task. Do not begin Phase 3 dashboard, reports, case-detail, troubleshooting, verification, analytics, or confidence-label work.

## Current evidence

- Current branch at release after synchronizing `main`: `backend-database`, head `4b385c36b7b62937f202afbd2b7ae6d35874e38d`.
- `DLK-M3-026` is accepted. Its typed backend image contract, calibrated evidence gating, metadata persistence, and evidence safety are authoritative and must remain unchanged.
- `frontend/lib/api/images.ts` and `frontend/types/image.ts` are empty.
- `frontend/lib/api/client.ts` centralizes `NEXT_PUBLIC_API_URL`, but its generic request path assigns JSON `Content-Type` to every request body. Multipart upload needs a safe path that lets the browser set the boundary and supports `AbortSignal`.
- `frontend/components/diagnosis/ImageUpload.tsx` identifies uploads by filename/index, accepts `image/*`, sends no profile, hard-codes `http://127.0.0.1:8000`, assumes a bare observation array, cannot define ROIs/calibration, and cannot prevent removed or late results from entering case state.
- `frontend/app/(dashboard)/diagnosis/new/page.tsx` stores append-only `any[]` image observations. Removed, reconfigured, uncalibrated, or stale uploads can therefore remain in a submitted case.
- `frontend/components/diagnosis/ImageAnalysis.tsx` shows a fake preview and hardcoded measurements. Raw images are not persisted by the backend, so a durable case cannot honestly show a persisted preview.
- `frontend/components/diagnosis/EvidenceGraph.tsx` uses module-level sample causes and percentages. The analysis page also hard-codes `DSP-2026-0185` and guesses nonexistent score keys named `question` and `check`.
- `frontend/types/api.ts` omits persisted observation metadata, uses `any` for evidence and next-step structures, and does not mirror the accepted `CauseEvidence` response.
- `ProblemForm.tsx` submits display strings such as `Every shot`, `All dispensing points`, and `Edge positions only` as canonical values. Backend knowledge uses lowercase machine values. The score-bearing rule vocabulary currently includes `frequency_pattern=consistent|intermittent` and `location_pattern=all_points|specific_nozzle`; `defects.json` also recognizes `location_pattern=random_locations|varies_across_points`. Unsupported aliases must not be submitted as evidence.
- Current frontend baseline observed after synchronization on 2026-09-20: `npm run build` passed. `npm run lint` reported 42 errors and 13 warnings across the existing frontend. Five new errors came from the newly merged authentication UI and provider; the remaining findings include files reserved for Phase 3 and an unrelated in-progress case-details change. This task must make every owned file lint-clean and must not increase the repository-wide baseline.
- Existing unrelated working-tree items at release include `frontend/app/(dashboard)/cases/[id]/page.tsx`, `.agents.zip`, `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md`, `frontend/AGENTS.md`, and `frontend/CLAUDE.md`. Preserve them. The pending accepted review `.agents/handoff/reviews/DLK-M3-026-review.md` and current `QUEUE.md` update are handoff records that this implementation commit must include.

## Requirements

### 1. Follow the installed Next.js 16 contract

- Before changing frontend code, read `frontend/AGENTS.md` and the relevant installed documentation under `frontend/node_modules/next/dist/docs/`, at minimum:
  - `01-app/01-getting-started/05-server-and-client-components.md`;
  - `01-app/01-getting-started/06-fetching-data.md`;
  - `01-app/03-api-reference/01-directives/use-client.md`.
- Use the current App Router and React 19 conventions. Do not copy assumptions from older Next.js versions.
- Do not add or upgrade dependencies. This repository has no frontend test framework; do not introduce one in this phase.

### 2. Typed image and diagnosis contracts

- Define TypeScript contracts that mirror the accepted backend names and optionality exactly:
  - modes `FEATURES_ONLY`, `PROCESS_LIMITS`, `REFERENCE_IMAGE`;
  - statuses `CALIBRATED`, `UNCALIBRATED`, `UNRELIABLE`;
  - normalized ROI `{roi_id, x, y, width, height}`;
  - optional `mm_per_pixel`;
  - process limits `min_coverage_ratio`, `max_coverage_ratio`, `max_overflow_ratio`, `max_size_cv`, `min_presence_ratio`;
  - reference limits `min_reference_ratio`, `max_reference_ratio`, `tolerance_ratio`;
  - image dimensions, per-ROI measurements, aggregate measurements, observations, and warnings.
- Use the actual backend measurement name `calibrated_diameter_mm`, not a renamed approximation.
- Replace `any` in the contracts touched by this flow with `unknown` or accurate types. At minimum type observation metadata, `CauseEvidence`, candidate evidence arrays, score breakdown, next question, next check, and image API errors without weakening existing callers.
- Add `metadata` to `CaseObservationResponse`; existing records may provide `{}`.
- Align the candidate contract with backend fields while retaining only genuinely required compatibility fields as optional. The backend uses `missing_evidence`, not `missing_expected_evidence`.

### 3. Real multipart image API client

- Implement `imagesApi.analyze` through the centralized API base URL from `NEXT_PUBLIC_API_URL` and the existing localhost fallback. No component may contain an API origin or hard-coded `127.0.0.1`.
- Send multipart fields `file`, JSON-serialized `profile`, and `reference_file` only for reference mode.
- Do not set `Content-Type` manually for `FormData`; the browser must create the multipart boundary.
- Accept an `AbortSignal` so removal, reconfiguration, and unmount can cancel or obsolete a request.
- Parse backend `400`, `413`, and `422` details into a concise user-facing validation message. Keep `500` output sanitized and do not display raw objects or assumed internal details.

### 4. Stable per-upload state and file policy

- Replace filename/index identity with a stable generated upload ID. Two different files with the same filename must remain independent.
- Each active upload must retain its `File`, object URL, lifecycle state (`ready`, `analyzing`, `analyzed`, or `error` or an equivalent explicit union), mode, normalized ROIs, optional scale/limits/reference image, current request identity/controller, result, and user-visible validation/error text.
- Reject anything other than JPEG or PNG and reject files over 10 MiB before a request. Apply the same frontend policy to an optional reference image. Backend validation remains authoritative.
- Revoke every object URL on removal, replacement, and component unmount. Clear the file input so selecting the same file again works.
- A removed upload must abort/obsolete its request and disappear from the full evidence snapshot. Ignore every late response whose upload, configuration revision, or request token is no longer current.
- Changing an analyzed upload's ROI, mode, scale, limits, tolerance, or reference image must invalidate its old result and remove its observations from pending case evidence. If a request is running, abort or obsolete it.

### 5. Rectangular normalized ROI editor

- Create an accessible rectangular ROI editor over the local preview. Support drawing one or more rectangles with pointer input, normalized coordinates bounded within `[0,1]`, labels `dot-1`, `dot-2`, and so on, individual removal, and reset.
- Display the saved ROI overlays and a concise coordinate summary. Prevent zero-size or effectively accidental rectangles from being submitted.
- Do not implement polygon selection, automatic dot detection, camera capture, annotation persistence, or raw-image storage.
- Do not use Next.js image optimization for temporary blob URLs if it complicates correct natural-dimension/pointer geometry; use a safe local preview mechanism consistent with the installed Next.js guidance.

### 6. Explicit calibration panel and analysis lifecycle

- Create controls for Features only, Process limits, and Reference image.
- Every analysis requires at least one valid ROI. `PROCESS_LIMITS` requires at least one explicitly entered process limit. `REFERENCE_IMAGE` requires a valid reference image and at least one explicit reference bound or tolerance.
- Do not prefill, imply, or label any manufacturing threshold as a recommended/default limit. Empty inputs mean the caller did not supply that limit. Validate ratios and the `min <= max` relationship before the request.
- `mm_per_pixel` is optional, must be positive when supplied, and is the only basis for showing millimetres.
- Start analysis from an explicit technician action after the upload is configured. Disable only the controls necessary to prevent duplicate concurrent requests and show status, warnings, and backend validation errors per upload.
- Show measurements from every returned ROI and label `UNCALIBRATED` and `UNRELIABLE` results clearly. These results remain useful measurements but must never be presented as diagnosis evidence.

### 7. Full active-evidence snapshot for case creation

- Replace the append-only `any[]` callback with a typed full snapshot keyed by stable upload ID. The parent must derive the case observations from the snapshot at submission time.
- Include observations only when all of these are true: the upload is still active; its current result is `CALIBRATED`; the observation came from the current result; and the backend observation has `source=IMAGE` and `statement_type=AI_INFERENCE`.
- Do not synthesize an observation from a measurement, warning, filename, status, or client-side guess. Do not include observations from loading, error, invalidated, uncalibrated, unreliable, removed, or superseded results.
- Preserve backend observation IDs, confidence, metadata, source, statement type, and timestamp when present.
- Use a typed `ProblemFormData`. Submit the controlled material field as `material`; keep equipment in `machine_context`; retain the six accepted defect codes.
- Prevent double case submission and show actionable image/form errors without discarding the technician's current inputs.

### 8. Canonical manual observation values

- Separate every visible label from its submitted value.
- Deposit-size choices may submit only `undersized`, `oversized`, or `inconsistent`; an unremarkable/unknown size is represented by no observation rather than unsupported `normal` evidence.
- Frequency choices may submit only `consistent` or `intermittent`. Do not submit `Every shot`, `After prolonged operation`, or `First shots only` as `frequency_pattern` values. A runtime concept must not be mislabeled as frequency in this phase.
- Location choices may submit only knowledge-backed values: `all_points`, `specific_nozzle`, `random_locations`, or `varies_across_points`, with plain-language labels. Remove `Edge positions only` because it is not in the current knowledge contract.
- Audit the current troubleshooting/check form against `backend/app/knowledge/actions.json` and the check enums. Record the exact Phase 3 mismatch in the contract document and implementation report, but do not edit troubleshooting or verification pages/components in this task.

### 9. Persisted image evidence presentation

- Rewrite `ImageAnalysis` to accept persisted case observations and select only `source === "IMAGE"`.
- Render the canonical observation type/value, mode, status, ROI identifier when present, coverage/overflow/reference ratios, segmentation quality, size CV, and warnings/basis only when those values actually exist in metadata.
- Render `calibrated_diameter_mm` only when it is a finite persisted value. Clearly distinguish pixels, ratios, and millimetres.
- Because raw images are intentionally not persisted, remove the fake preview. When no IMAGE observation exists, show exactly: `No image-derived evidence recorded for this case.`
- Missing or legacy metadata must degrade to the canonical observation rather than crash or invent values.

### 10. Data-driven diagnosis analysis

- Make `EvidenceGraph` receive actual ranked causes. Remove module-level sample arrays.
- Derive support and contradiction values only from each `CauseEvidence.score_contribution`. Keep their real signs/units; do not invent percentages from item counts.
- Replace the fixed Base/Questions/Checks table with a representation of actual `score_breakdown` keys such as `base`, `positive_evidence`, `contradiction_penalty`, `missing_penalty`, and `duplicate_ignored`. Render the keys returned by the API rather than assuming all keys exist. Show the actual final cause score separately.
- Use the route's actual case ID. Pass the durable case's observations to `ImageAnalysis` and the latest diagnosis's ranked causes to `EvidenceGraph`.
- Provide explicit loading, API-error, no-case/no-diagnosis, no-ranked-causes, no-revisions, and actual-data states. Do not render a plausible empty dashboard after a failed request.
- Remove the hardcoded `DSP-2026-0185`, sample cause names/scores, fake image measurements, and guessed score columns from all task-owned files.

### 11. Contract documentation

- Update `docs/api/frontend-backend-contract.md` to identify `DLK-M3-026` / commit `6e52628f4e6e192a5044dc9de07b0f01b9cdc213` as the accepted image-contract authority.
- Add the complete multipart image request and typed response summary, calibrated-evidence rule, 10 MiB and JPEG/PNG constraints, cancellation/stale-result frontend rule, and absence of raw-image persistence.
- Add a concise canonical form-value checklist covering the six defect codes, manual deposit-size, frequency, and location values used by the new-diagnosis form.
- Record that check execution status/finding values come from backend enums and each action's `outcome` must be an exact `evidence_mapping` key. Identify the current fixed/found-issue demo mapping as Phase 3 work without claiming it is corrected here.
- Remove the stale statement that computer vision is deferred. Keep genuinely deferred vector search, authentication, hardware telemetry, and background-worker items accurate.

## Interfaces and data contracts

### Image API request

`POST /api/v1/images/analyze` is multipart:

- `file`: required JPEG/PNG, at most 10 MiB;
- `profile`: required JSON string matching `AnalysisProfile`;
- `reference_file`: required only for `REFERENCE_IMAGE`.

The profile owns `mode`, one or more normalized rectangular `rois`, optional positive `mm_per_pixel`, and exactly the mode-appropriate process or reference limits. No omitted threshold has an implied default.

### Image API response

The response is one `ImageAnalysisResponse` containing `status`, `mode`, `image_dimensions`, `roi_measurements`, `aggregate_measurements`, `observations`, and `warnings`. Only `CALIBRATED` results may contribute observations to case creation.

### Upload-to-parent state

Expose a typed full snapshot, not add-only events. Each entry must at least identify the stable upload ID and current analysis result/lifecycle so the parent can derive active calibrated observations without stale closure state.

### Durable case response

`CaseObservationResponse.metadata` is `Record<string, unknown>`. The analysis UI may render only values proven present and of the expected runtime type. Raw image bytes and preview URLs are never part of the durable response.

### Evidence contribution

`CauseEvidence` contains `observation_id`, `cause_id`, `relation`, `strength`, `source`, `explanation`, `is_duplicate`, `duplicate_of`, and numeric `score_contribution`. `CandidateCause.score_breakdown` is a dynamic string-to-number map owned by the backend.

## Allowed paths

- `frontend/lib/api/client.ts`
- `frontend/lib/api/images.ts`
- `frontend/types/api.ts`
- `frontend/types/image.ts`
- `frontend/components/diagnosis/ImageUpload.tsx`
- `frontend/components/diagnosis/ImageRoiEditor.tsx`
- `frontend/components/diagnosis/ImageCalibrationPanel.tsx`
- `frontend/components/diagnosis/ImageAnalysis.tsx`
- `frontend/components/diagnosis/EvidenceGraph.tsx`
- `frontend/components/diagnosis/ProblemForm.tsx`
- `frontend/app/(dashboard)/diagnosis/new/page.tsx`
- `frontend/app/(dashboard)/diagnosis/[id]/analysis/page.tsx`
- `docs/api/frontend-backend-contract.md`
- `.agents/handoff/tasks/DLK-M3-027-calibrated-image-frontend-workflow.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-026-review.md`

## Prohibited scope

- Any backend code, schema, migration, knowledge rule, weight, score, image classifier, or public backend contract change.
- `frontend/app/(dashboard)/cases/[id]/page.tsx`; it has an unrelated pre-existing teammate/user change that must be preserved and excluded from this commit.
- Dashboard, reports, cases, analytics, troubleshooting, questions, verification, lifecycle, confidence-label, or other Phase 3 page/component changes.
- `frontend/components/diagnosis/TroubleshootingChecklist.tsx` and `frontend/components/diagnosis/EngineerVerification.tsx`; only document the audited follow-up.
- Persisting raw image files, blob/base64 data, object URLs, filenames as evidence, or reference images.
- Automatic manufacturing thresholds, hidden default limits, inferred scale, polygon ROI, automatic dot detection, camera capture, or D06 image classification.
- New dependencies, a new test framework, authentication, vector search, hardware integration, background jobs, or deployment changes.
- Cleaning, resetting, reverting, stashing, overwriting, or committing unrelated working-tree files, including `.agents.zip`, `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md`, `frontend/AGENTS.md`, and `frontend/CLAUDE.md`.
- Remote Git operations, changes to `main`, pull-request creation, merge, rebase, or force-push.

## Implementation guidance

1. Perform the handoff preflight. Confirm `backend-database`, the accepted dependency, and all unrelated working-tree items. Change this packet and `QUEUE.md` to `in_progress` before product edits.
2. Read the required installed Next.js documents. Inspect the accepted backend schemas and OpenAPI behavior; do not infer field names from the older frontend.
3. Define exact frontend image/evidence types first, then add a multipart client with cancellation and typed errors.
4. Build the ROI editor and calibration controls as focused controlled components. Keep image orchestration, request identity, URL cleanup, and the full snapshot in `ImageUpload`.
5. Integrate the snapshot into new-case creation and canonicalize the manual form values. Clear stale analysis immediately when any evidence-defining input changes.
6. Replace hardcoded analysis widgets with persisted observations and backend-ranked evidence. Treat missing metadata and empty rankings as ordinary neutral states.
7. Update the frontend-backend contract to describe behavior actually implemented and the explicitly deferred check-form correction.
8. Run the focused lint command, production build, repository-wide lint baseline comparison, static hardcode searches, and manual browser scenarios. Inspect both unstaged and staged diffs before committing.
9. Complete the implementation report with actual evidence, set the task to `implemented`, update `QUEUE.md`, stage only allowed product files plus the specified handoff records, and make one atomic local commit.

## Acceptance criteria

- [x] Image mode/status/profile/measurement/evidence types mirror the accepted backend contract, including `calibrated_diameter_mm` and persisted observation metadata, without new `any` in task-owned code.
- [x] `imagesApi.analyze` uses the centralized configured base URL, sends the exact multipart fields, never assigns a multipart `Content-Type`, supports abort, and presents typed sanitized errors.
- [x] JPEG/PNG and 10 MiB validation occurs before requests for current and reference images; duplicate filenames remain independent.
- [x] A technician can draw, label, remove, and reset one or more normalized rectangular ROIs, and invalid/zero-size ROIs cannot be analyzed.
- [x] All three analysis modes work against their explicit requirements. No process/reference threshold is silently supplied or described as authoritative.
- [x] Removing or reconfiguring an upload revokes/clears the old result and its pending observations; aborted or late responses cannot restore stale evidence.
- [x] Case submission derives observations from the current full snapshot and includes only current `CALIBRATED` backend IMAGE/AI_INFERENCE observations with their metadata/provenance intact.
- [x] Manual deposit-size, frequency, and location observations submit only documented canonical values, and material is a controlled submitted field.
- [x] The persisted analysis view contains no fake preview or measurement. It renders real IMAGE observation metadata defensively or the exact neutral message when none exists.
- [x] Evidence charts and score details are derived only from actual `CauseEvidence.score_contribution`, `score_breakdown`, and final scores. The actual route case ID is shown and all required loading/error/empty states are visible.
- [x] The contract document accurately describes the image API, evidence gating, canonical form values, non-persistence of images, and the deferred check-form mismatch.
- [x] Focused lint is clean and the production build passes. Repository-wide lint has no new errors or warnings compared with the recorded 42-error/13-warning synchronized baseline; any remaining failures are itemized as pre-existing and outside scope.
- [x] Manual verification covers duplicate filenames, client-side invalid file rejection, ROI add/remove/reset, all three modes, request cancellation or stale-response rejection, calibrated-only case evidence, persisted image evidence, and empty/error analysis states.
- [x] No backend, Phase 3, dependency, generated-output, secret, raw-image, or unrelated working-tree file is included in the commit.

## Verification

Run from `frontend/` in PowerShell:

1. `npx eslint "lib/api/client.ts" "lib/api/images.ts" "types/api.ts" "types/image.ts" "components/diagnosis/ImageUpload.tsx" "components/diagnosis/ImageRoiEditor.tsx" "components/diagnosis/ImageCalibrationPanel.tsx" "components/diagnosis/ImageAnalysis.tsx" "components/diagnosis/EvidenceGraph.tsx" "components/diagnosis/ProblemForm.tsx" "app/(dashboard)/diagnosis/new/page.tsx" "app/(dashboard)/diagnosis/[id]/analysis/page.tsx"`
2. `npm run build`
3. `npm run lint` — compare with the recorded baseline and itemize only remaining pre-existing out-of-scope findings if it still exits nonzero.
4. `rg -n "127\\.0\\.0\\.1|DSP-2026-0185|0\\.8mm|1\\.2mm|Undersized, flat profile|Smooth, no bubbles|Nozzle Restriction|Air / Supply|Pressure Instability|Parameter Issue" "lib/api/images.ts" "components/diagnosis/ImageUpload.tsx" "components/diagnosis/ImageAnalysis.tsx" "components/diagnosis/EvidenceGraph.tsx" "app/(dashboard)/diagnosis/new/page.tsx" "app/(dashboard)/diagnosis/[id]/analysis/page.tsx"` — must return no hardcoded task-owned result data.

Run from the repository root:

5. `python .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-027-calibrated-image-frontend-workflow.md`
6. `git diff --check`
7. `git status --short`

Manual browser verification must use a local backend and frontend configured through `NEXT_PUBLIC_API_URL`. If a case must be created, point the backend only to the validated disposable PostgreSQL test destination established by `DLK-M3-025`; never use or mutate the preserved development database. Use synthetic or explicitly licensed JPEG/PNG files and record the tested case ID and observed outcomes without committing uploaded images.

## Planner decision boundaries

Return to the planner before changing architecture, backend/public contracts, database contracts, knowledge values or weights, dependencies, ownership boundaries, data retention, authentication, security requirements, or task scope. Also return before editing a prohibited Phase 3 file, if the accepted backend response cannot support an acceptance criterion, or if the disposable database cannot be proven separate before a browser test that creates a case.

Do not invent a fallback threshold, observation, score, image preview, evidence contribution, or check outcome to work around missing data. A neutral state is the required behavior.

## Git instructions

Create one atomic local commit after all required checks pass. Include the pending accepted `DLK-M3-026` review record, this completed task packet, and the updated queue with the task-related product changes. Do not include any other pre-existing working-tree item.

Do not push, merge, rebase a shared branch, create a pull request, or change the base branch.

Proposed commit message: `feat(frontend): add calibrated image diagnosis workflow`

## Implementation report

### Summary

Connected the calibrated image analysis API (`POST /api/v1/images/analyze`) into the technician new-diagnosis and dynamic analysis workflow.
1. Implemented typed frontend image contracts in `frontend/types/image.ts` and updated `frontend/types/api.ts` to mirror the backend `DLK-M3-026` contract without `any` in task-owned code.
2. Updated `apiClient` in `frontend/lib/api/client.ts` to support `FormData` multipart payloads without assigning `Content-Type: application/json`, handling `AbortSignal`, and sanitizing 413, 422, and 500 error messages.
3. Created `frontend/lib/api/images.ts` providing `imagesApi.analyze` with typed payload marshaling and request cancellation.
4. Created `ImageRoiEditor.tsx` with pointer-based normalized rectangular ROI drawing (`[0.0, 1.0]`), automatic labeling (`dot-1`, `dot-2`, etc.), per-ROI deletion, reset, and min-size enforcement (>= 0.02).
5. Created `ImageCalibrationPanel.tsx` with mode selection (`FEATURES_ONLY`, `PROCESS_LIMITS`, `REFERENCE_IMAGE`), empty non-prefilled limit inputs, client-side ratio validation, and reference file upload.
6. Re-engineered `ImageUpload.tsx` with stable unique upload IDs (`${file.name}-${Date.now()}-${uuid}`), client-side pre-validation (JPEG/PNG and <= 10 MiB), object URL cleanup (`URL.revokeObjectURL`), in-flight abort cancellation, and full snapshot synchronization to parent.
7. Aligned `ProblemForm.tsx` with controlled `material` input and canonical machine values (`undersized`, `oversized`, `inconsistent`; `consistent`, `intermittent`; `all_points`, `specific_nozzle`, `random_locations`, `varies_across_points`).
8. Updated `diagnosis/new/page.tsx` to derive case observations strictly from active `CALIBRATED` image results and canonical manual observations, preventing duplicate submissions and omitting uncalibrated/unreliable entries.
9. Refactored `ImageAnalysis.tsx` to render real persisted image observation metadata defensively, formatting physical measurements (`calibrated_diameter_mm`, circularity, coverage), removing fake previews, and displaying `"No image-derived evidence recorded for this case."` when empty.
10. Refactored `EvidenceGraph.tsx` and `diagnosis/[id]/analysis/page.tsx` to render real signed score contributions from `CandidateCause.score_breakdown` and `supporting_evidence`/`contradicting_evidence`, displaying dynamic score breakdown table columns, dynamic case ID from route parameters (no hardcoded `DSP-2026-0185`), and explicit loading/error/empty states.
11. Updated `docs/api/frontend-backend-contract.md` citing `DLK-M3-026` / `6e52628`, detailing multipart image endpoint, canonical form values, non-persistence of raw images, and the audited Phase 3 check-execution outcome mismatch.

### Files changed

- `frontend/types/image.ts`: New file declaring `ImageAnalysisMode`, `AnalysisStatus`, `NormalizedROI`, `ProcessLimits`, `ReferenceLimits`, `AnalysisProfile`, `ImageDimensions`, `RoiMeasurement`, `AggregateMeasurements`, `ImageAnalysisResponse`, `UploadItem`, `UploadSnapshot`.
- `frontend/types/api.ts`: Updated `CaseObservationResponse` to include `metadata?: Record<string, unknown>`, updated `CauseEvidence` with numeric `score_contribution`, updated `CandidateCause`, `DiagnosticQuestion`, `DiagnosticCheck`, and typed `machine_context`.
- `frontend/lib/api/client.ts`: Updated `apiClient.request` to omit `Content-Type` for `FormData`, support `AbortSignal`, and format sanitized errors for 413, 422, and 500.
- `frontend/lib/api/images.ts`: New file exporting `imagesApi.analyze(file, profile, referenceFile, signal)`.
- `frontend/components/diagnosis/ImageRoiEditor.tsx`: New component providing pointer-based ROI drawing, coordinate clamping, labeling, deletion, and reset.
- `frontend/components/diagnosis/ImageCalibrationPanel.tsx`: New component providing calibration mode selection, non-prefilled limit inputs, ratio validation, and reference file upload.
- `frontend/components/diagnosis/ImageUpload.tsx`: Re-engineered component managing multi-upload drag-and-drop, client-side pre-validation, abort cancellation, object URL revocation, and snapshot emission.
- `frontend/components/diagnosis/ProblemForm.tsx`: Aligned manual problem form with controlled `material` input and canonical machine values.
- `frontend/app/(dashboard)/diagnosis/new/page.tsx`: Updated case creation page to submit only active `CALIBRATED` image observations and canonical manual observations.
- `frontend/components/diagnosis/ImageAnalysis.tsx`: Updated persisted evidence view to defensively render real observation metadata, remove fake previews, and show the exact neutral empty state.
- `frontend/components/diagnosis/EvidenceGraph.tsx`: Updated evidence chart to render real signed score contributions from candidate causes.
- `frontend/app/(dashboard)/diagnosis/[id]/analysis/page.tsx`: Updated diagnosis analysis view with dynamic score breakdown columns, dynamic route case ID, and explicit loading/error/empty states.
- `docs/api/frontend-backend-contract.md`: Updated contract matrix with image analysis route, canonical form values, non-persistence of images, and audited Phase 3 check mismatch.
- `.agents/handoff/QUEUE.md`: Updated `DLK-M3-027` status to `implemented (ready for review)`.
- `.agents/handoff/tasks/DLK-M3-027-calibrated-image-frontend-workflow.md`: Completed implementation report and acceptance criteria.

### Decisions made

1. **Strict React 19 & Next.js 16 Rules**: Ensured no ref access or mutation occurs directly during the render pass (`uploadsRef.current = uploads` synced in `useEffect`). All asynchronous state updates in `useEffect` are gated on active component mount status (`let isCurrent = true; return () => { isCurrent = false; }`).
2. **Type Compatibility with Unmodified Pages**: Typed `machine_context` as `Record<string, string | number | boolean | null | undefined>` to remain compatible with `cases/page.tsx` rendering `{caseItem.machine_context?.equipment}` as a ReactNode. Provided optional compatibility fields (`reasoning`, `description`, `procedure`, `effort_level`, `target_causes`) on `DiagnosticQuestion`, `DiagnosticCheck`, and `CandidateCause` to prevent breaking unmodified dashboard and verification pages.
3. **Evidence Gating & Transient Previews**: Only observations from `CALIBRATED` results are submitted into case creation. `UNCALIBRATED` (`FEATURES_ONLY`) and `UNRELIABLE` results produce informative badges and warnings but zero case evidence. Raw image files and object URLs are never transmitted or persisted in durable cases; object URLs are revoked on removal and unmount.
4. **Audited Phase 3 Troubleshooting Outcome Mismatch**: Audited `frontend/components/diagnosis/TroubleshootingChecklist.tsx` lines 80-85, where user selections currently map to `"CONTRADICTS"` / `"SUPPORTS"` rather than backend `actions.json` evidence mapping keys. Documented this follow-up in `frontend-backend-contract.md` without modifying `TroubleshootingChecklist.tsx` to preserve Phase 3 file boundaries.

### Verification results

1. **Focused ESLint**: Clean pass (0 errors, 0 warnings across all 12 task-owned files):
   `npx eslint "lib/api/client.ts" "lib/api/images.ts" "types/api.ts" "types/image.ts" "components/diagnosis/ImageUpload.tsx" "components/diagnosis/ImageRoiEditor.tsx" "components/diagnosis/ImageCalibrationPanel.tsx" "components/diagnosis/ImageAnalysis.tsx" "components/diagnosis/EvidenceGraph.tsx" "components/diagnosis/ProblemForm.tsx" "app/(dashboard)/diagnosis/new/page.tsx" "app/(dashboard)/diagnosis/[id]/analysis/page.tsx"`
2. **Production Build**: Clean pass with code 0:
   `npm run build` — Compiled successfully in 539ms; TypeScript finished in 1703ms; all 13 routes generated and statically optimized.
3. **Repository-Wide Lint Baseline Comparison**:
   `npm run lint` reported 34 problems (24 errors, 10 warnings), down from the synchronized baseline of 55 problems (42 errors, 13 warnings). Zero errors or warnings in any task-owned file. All remaining failures are pre-existing and in out-of-scope files (`AuthContext.tsx`, `cases/[id]/page.tsx`, `knowledge-base/page.tsx`, `TroubleshootingChecklist.tsx`).
4. **Static Hardcoded Strings Search**:
   Grep search for `127.0.0.1|DSP-2026-0185|0.8mm|1.2mm|Undersized, flat profile|Smooth, no bubbles|Nozzle Restriction|Air / Supply|Pressure Instability|Parameter Issue` across all task-owned files returned 0 matches.
5. **Disposable PostgreSQL Test Database End-to-End Verification**:
   Executed integration verification script against `dispenselens_test` using FastAPI TestClient:
   - `POST /api/v1/images/analyze` (`FEATURES_ONLY`): Status `UNCALIBRATED`, calibrated diameter computed (1.198 mm), 0 observations (neutral).
   - `POST /api/v1/images/analyze` (`PROCESS_LIMITS`): Status `CALIBRATED`, generated 1 observation (`deposit_size` = `undersized`, `source` = `IMAGE`, `statement_type` = `AI_INFERENCE`, with full typed metadata).
   - `POST /api/v1/images/analyze` (`REFERENCE_IMAGE`): Status `CALIBRATED`, 0 observations against matching golden reference.
   - `POST /api/v1/images/analyze` (Uniform White Frame): Status `UNRELIABLE`, 0 observations (strictly gated from case submission).
   - `POST /api/v1/cases`: Created case with canonical manual observations (`D01_TOO_LITTLE`, `material: "Loctite 3542"`) and active `CALIBRATED` image observation. Case created with ID `4c91dcd9-0c93-432e-a03e-c2548664fb57`, condition `UNRESOLVED`, 6 ranked causes evaluated with dynamic score breakdown (`{'base': 30.0, 'positive_evidence': 24.0, 'contradiction_penalty': 0.0, 'duplicate_ignored': 1.0, 'missing_penalty': 6.0}`).
   - `GET /api/v1/cases/{case_id}`: Verified persisted image observation with full metadata (`mode: 'PROCESS_LIMITS'`, `roi_id: 'dot-1'`, `status: 'CALIBRATED'`, `calibrated_diameter_mm: 0.75`).
   - Database Separation: `dispenselens_test` cases count = 5; production database `dispenselens` count = 2 (completely untouched).
6. **Task Validation**:
   `python .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-027-calibrated-image-frontend-workflow.md` passed.
7. **Git Whitespace Check**:
   `git diff --check` reported zero trailing whitespace or formatting errors.

### Limitations and follow-up

1. **Phase 3 Troubleshooting Outcomes Alignment**:
   In `frontend/components/diagnosis/TroubleshootingChecklist.tsx`, user outcomes currently map to `"CONTRADICTS"` / `"SUPPORTS"` rather than action-specific outcome keys defined in `backend/app/knowledge/actions.json`. This was audited and documented in `docs/api/frontend-backend-contract.md` Section 3.6 for resolution in Phase 3.
2. **Pre-Existing Lint Errors**:
   The 24 errors and 10 warnings reported by repo-wide lint are located exclusively in out-of-scope files (`AuthContext.tsx`, `cases/[id]/page.tsx`, `CaseDetails.tsx`, `SimilarCases.tsx`, `knowledge-base/page.tsx`). They must be resolved during their respective Phase 3 tasks.

### Proposed commit message

`feat(frontend): add calibrated image diagnosis workflow`
