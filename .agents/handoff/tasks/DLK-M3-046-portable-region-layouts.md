---
task_id: DLK-M3-046
title: Save and load portable region layouts with manual confirmation
status: blocked
created_by: ChatGPT planner
assigned_to: GPT-6 Luna implementer
depends_on: [DLK-M3-045]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-046: Portable region layouts

## Takeover instructions — 2026-10-02

Resume this existing task, not a new feature. User now assigns implementation to GPT-6 Luna and independent review to GPT-6 Astra or GPT-6 Sol. This section supersedes historical Gemini-specific execution instructions and stale completion claims below. Read `.agents/handoff/reviews/DLK-M3-046-review.md` before modifying code. Final acceptance remains outstanding.

### Preserve and inspect the current work

HEAD at planning inspection is `bf72c0a8cf30d694713909f01f85ed3388b63c4b`. Four frontend files have uncommitted corrections: ImageUpload.tsx, RegionLayoutControls.tsx, image-upload-state.ts and test-image-upload-state.mjs. Preserve and inspect them; do not reset, stash, overwrite or reimplement from the committed version. There are also pending handoff records. Do not stage unrelated `.agents.zip`, `scratch/` or PROJECT-PROGRESS-2026-09-19.md.

Before editing, ensure Antigravity's implementation agent has stopped writing. Reuse identified existing services if healthy; a server may keep running without implying another agent is editing. Do not kill arbitrary Node/Python/Docker processes. If concurrent editing is ongoing, pause the takeover and report the conflict.

### Remaining implementation and evidence

1. Reassess R1 against the working tree: cancellation now precedes oversized-file rejection and a token is passed into a state updater. Do not repeat already completed work. Finish the end-to-end import guard, including out-of-order A/B reads, oversized B after delayed A, edit/abandon/delete during a read, late errors, teardown and inline/studio coordination. Test the actual integration path, not a separately simulated check.
2. Make React state updates replay-safe. The current `setUploads` callback calls `ImportCoordinator.commitImport`, which consumes/cancels the session, aborts an analysis and calls setLayoutErrors. Replayed updater evaluation can then see a consumed token and return the previous snapshot instead of the import. Keep state transitions pure and deterministic, retaining atomic current-state revision/token validation; move external cleanup out of updater evaluation. Verify repeated evaluation from identical prior state and the real development/Strict Mode UI. Do not disable Strict Mode to pass.
3. Preserve R2's current unconditional dimension validation and regressions for null/undefined/nonpositive/nonfinite dimensions. Verify analysis stays blocked until placement can be confirmed.
4. Complete R3 evidence exactly as required below: actual save/download/reimport, invalid file, mismatch, edit-after-confirmation, keyboard controls, delayed races, inline/studio parity and one real image-analysis round trip. Capture request/response to the actual `/api/v1/images/analyze` endpoint, match ROI IDs and verify no dispatch while unconfirmed. Never infer HTTP success from page headings. Record real service identity and tested revision; separate mocked checks from live checks.
5. Replace the historical implementation report's unsupported endpoint, response fields and pass claims with new measured results. Re-run the focused Node scripts, lint, build, browser checks and task validation listed below. Do not carry old test totals forward as evidence of this correction. If a required check remains unavailable, report it explicitly and leave the task blocked; finish independent code/test work first.

### Bounded service diagnosis — no indefinite waits

An empty Antigravity `curl -s` log is inconclusive; it does not establish backend health, database failure or an application bug. Use explicit executable and bounded visible output, from PowerShell:

`curl.exe --silent --show-error --connect-timeout 3 --max-time 10 --write-out '\nHTTP %{http_code}\n' http://127.0.0.1:8000/api/v1/health`

Record `$LASTEXITCODE` immediately. If curl.exe is unavailable, use `Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 10` with visible error handling. Expected body identifies `service: dispense-lens-api`; health verifies process responsiveness only, not database readiness.

On failure, inspect port 8000 ownership and backend startup logs before starting a second process. Use the existing startup runbook/configuration; never print secrets. If backend is absent, start the documented local service with logs captured and observe startup for at most 60 seconds before recording a diagnostic failure. Use at most three bounded health attempts per diagnostic cycle; change or investigate the cause before retrying. Treat frontend/backend dev servers as persistent services, not commands that should finish. Never loop silently overnight. Keep port 3001 for this frontend; port 3000 may host another application. Do not delete database volumes, migrate/reset development data, install dependencies or alter production backend code to evade a failed check; report prerequisites or a narrowly evidenced blocker.

### Completion and reviewer handoff

Remain within the original allowed implementation paths. Additionally allowed: this takeover's PROJECT.md/QUEUE.md and DLK-M3-046-review.md records; preserve the review's historical findings and leave acceptance to the reviewer. Complete one scoped local correction commit after checks. Report commit hash, actual results, remaining limitations and review entry point. Do not push, create a PR or merge. Independent Astra/Sol review must inspect the full original implementation plus correction, verify R1–R3 and update the permanent review/queue. The implementer must not mark itself accepted.

Current scope estimate remains manual-region prototype 90–95%, full improvement roadmap 65–75%; no increase until reviewed. Broader product features remain outside this takeover.

## Objective

Let a technician save expected region positions from the existing image workbench, load them onto another image, inspect their placement and explicitly confirm before analysis. This is the first bounded Phase 3 product increment: geometry-only layout reuse, without automatic alignment or shared storage.

## Current evidence

- DLK-M3-045 is accepted at `75e61eac82db04279697856d64aa972c798b7e6d`; pending accepted review and queue edits belong in this implementation commit.
- On 2026-10-02 the user selected portable save/load files with manual confirmation rather than database profiles and authorized GPT-6 Luna to take over implementation.
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
- `frontend/scripts/verify-portable-layouts-browser.mjs` (bounded Chromium/CDP workflow verification and actual network capture)
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
5. Document geometry-only scope, file limits, positioning confirmation, separately reviewed calibration/thresholds/reference, and manual recovery after a rejected import. Correct the stale roadmap checkpoint without overstating completion. Leave 046 blocked if the required live API verification cannot run.

## Acceptance criteria

- [x] Save/load round-trip retains valid ordered ROIs and source dimensions without embedding images, calibration or results.
- [x] Invalid, unknown-version and oversized inputs fail without altering the upload or publishing stale evidence.
- [x] A valid import shows pending regions, invalidates old analysis and blocks every analysis path until placement confirmation.
- [x] Geometry/reference changes and competing/late operations cannot preserve or restore inappropriate confirmation/results; other uploads remain independent.
- [x] Dimension mismatch is visible, confirmation is explicit, and no automatic alignment/calibration transfer is claimed.
- [x] Manual-only flow and inline/studio accessibility remain intact; clearing imported regions provides a usable manual fallback.
- [ ] Focused tests, lint/build and recorded browser checks pass; only allowed files are committed locally.

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

### Outcome and state

The portable-layout implementation and browser UI checks are complete in the local working tree. The task remains **blocked**, not implemented or accepted, because the required unmocked analysis request did not receive an HTTP response. A local review-only correction commit will preserve the work for independent Astra/Sol inspection; no push or merge is authorized.

### Changes and behavior verified

- Added per-upload asynchronous import coordination with monotonic request tokens and captured configuration revisions. New selections cancel older reads before file-size validation; stale results/errors are ignored after edits, replacement imports, abandonment, deletion, or teardown.
- Made the import transition deterministic under React updater replay. The updater now computes the next snapshot without consuming the token or performing external cleanup; cleanup occurs after React exposes the committed revision/token.
- Placement confirmation now requires positive safe-integer decoded target dimensions; omitted, null, invalid and nonpositive dimensions remain blocked.
- Added `frontend/scripts/verify-portable-layouts-browser.mjs`, which uses real Chromium file inputs and downloads, checks invalid import, source/target mismatch, no dispatch while unconfirmed, confirmation, Studio parity/edit invalidation, and manual fallback. It captures the real analysis request instead of inferring success from page text.

### Verification run in this takeover

- `node --experimental-strip-types scripts/test-region-layout.mjs` — **9/9 passed**.
- `node --experimental-strip-types scripts/test-image-upload-state.mjs` — **21/21 passed**, including updater replay, synchronous file-read completion, absent dimensions, stale reads, A/B imports, edits, deletion, teardown, and oversized replacement.
- `node --experimental-strip-types scripts/test-region-inspection-view.mjs` — **6/6 passed**.
- `npm run lint` — **0 errors and 142 warnings** across the existing frontend; changed implementation files also pass a file-scoped lint check with no warnings.
- `npm run build` — TypeScript and Next.js build succeeded; 20 application routes generated.
- `node scripts/verify-portable-layouts-browser.mjs` — actual save/download produced `dispense-region-layout.json`; the downloaded file was imported into a 1024×768 image after an invalid-file check. The 800×600 source mismatch displayed, Analyze stayed blocked and added no request while unconfirmed, confirmation enabled the request, Studio reflected the same state, a Studio geometry edit invalidated confirmation, and manual abandonment cleared the import gate. Escape and Enter keyboard actions passed.
- Live request evidence: after confirmation, Chromium sent `POST http://127.0.0.1:8000/api/v1/images/analyze`; the multipart request contained the saved ROI ID. Chromium reported `net::ERR_CONNECTION_REFUSED`, so there is no HTTP status, response body, service identity, or successful measurement to report. This is **not** a passing live API round trip.
- Bounded service diagnosis: `/api/v1/health` returned HTTP 000 with `curl.exe` exit 7; Docker could not open its engine pipe; PostgreSQL at the configured local port 5432 was unreachable; Windows denied opening the installed `com.docker.service` even when service-start permission was requested. No database volume or record was modified.
- Task validation returned `VALID`; pre-commit `git diff --check` passed. The post-commit diff check is reported with the local review snapshot.

### Acceptance status

The geometry contract, import/export behavior, state guards, confirmation and browser UI paths passed their focused checks. The final acceptance item remains unchecked because the required live API round trip is unavailable. Keep DLK-M3-046 blocked until the backend/PostgreSQL service is available and a successful response can be captured with the service identity and response measurement for the submitted ROI ID. The existing review remains `changes_requested`; only an independent Astra/Sol reviewer may accept the task.

### Scope and follow-up

The estimates remain manual-region prototype **90–95%** and full roadmap **65–75%**, as scope estimates rather than accuracy. Later stages in `REGION-INSPECTION-COMPLETION-PLAN.md` remain unreleased. No production accuracy is claimed from synthetic browser fixtures.

### Proposed local commit message

`fix(vision): guard portable region imports against stale state`
