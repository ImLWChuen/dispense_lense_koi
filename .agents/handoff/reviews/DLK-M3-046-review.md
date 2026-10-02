---
task_id: DLK-M3-046
reviewed_commit: bf72c0a8cf30d694713909f01f85ed3388b63c4b
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-046

## Decision

Working-tree follow-up on 2026-10-02 (HEAD remains bf72c0a8cf30d694713909f01f85ed3388b63c4b): corrections are present but uncommitted. R2 is addressed in source with unconditional dimension validation and null/undefined regression assertions. R1 now uses a shared coordinator, but selecting an oversized replacement file returns before cancelling the existing import in ImageUpload.tsx:216–226. Reproduction by code path: start delayed valid import A, select oversized B, observe rejection, then let A finish; A is still active and replaces the layout despite the newer selection. Invalidate the prior session before any selected-file validation and cover this actual parent selection path. Preserve state/results when B is rejected. Also complete the originally requested atomic latest-state/token/revision check at the state-commit boundary: the current onCommit callback applies importRegionLayout directly, while ImportCoordinator.commitImport is unused by the UI and the session is cancelled before onCommit. Do not rely solely on the effect-synchronized uploadsRef before queuing a state update.

R3 remains outstanding: the task implementation report still contains the original unsupported endpoint/response and rehearsal claims; no revised verification is recorded for these working-tree corrections. This is a provisional source review, not acceptance of a new commit or a claim that new tests ran. Working-tree whitespace check passes. Complete R1/R3, rerun checks, correct the implementation report and commit locally before final acceptance. Decision remains changes_requested; scope estimates unchanged.

## Initial committed review

Changes requested. Strict geometry-only parsing, result invalidation on import, and visible placement confirmation are delivered, but asynchronous import protection and verification evidence do not yet satisfy the task. Reviewer inspected the committed changes and local rehearsal script; execution remains with Gemini. Committed whitespace check passed. Gemini reports layout 9/9, upload-state 14/14 and region-view 6/6 tests passing, lint with zero errors and 143 warnings, and a successful build; these were not independently rerun.

## Findings

### R1 — P1: File-reader stale checks compare the same captured upload object

`frontend/components/diagnosis/RegionLayoutControls.tsx:109–136` captures uploadItem/currentRevision and then compares that same render's uploadItem inside onload. React replacement state cannot update this closure. Consequently an old read completing after an ROI edit, a newer import, or abandonment can overwrite the newer geometry and clear its results. No monotonic read identity exists; inline and studio each create independent readers, and no unmount cleanup aborts them. `ImageUpload.tsx` handleImportLayout accepts any completed layout without an expected revision/token guard. The unit race simulation checks a fresh state variable externally and therefore does not exercise the broken callback path.

Own import request identity per upload in shared parent/state logic. Capture revision at selection, check latest upload existence/revision and latest import token atomically at commit, and ignore obsolete success/error callbacks. Invalidate pending reads on a subsequent selection, relevant edits, abandonment, deletion and teardown; share arbitration across inline/studio. Abort/clean up readers on teardown without allowing their callbacks to mutate state. Add regressions through the actual asynchronous import coordination for A/B out-of-order completion, an edit during read, abandonment/deletion during read, and cross-view reads. Preserve invalid/cancelled input no-mutation behavior.

### R2 — P2: Missing target dimensions bypass the confirmation helper

`frontend/lib/image-upload-state.ts` confirmRegionPlacement only validates dimensions when neither undefined nor null; both missing values proceed to confirmed=true. The component disables its button but the shared state transition remains fail-open, contrary to the required testable confirmation boundary. Require valid positive safe-integer target dimensions unconditionally. Add null, omitted, invalid and valid dimension regressions; unavailable dimensions must leave confirmation false and analysis blocked. Existing tests cover zero dimensions but omit null/undefined.

### R3 — P2: Rehearsal evidence does not prove the claimed live API response or race behavior

The implementation report claims a 200 response from `/api/v1/vision/analyze` with dispense_detected; the application mounts `/images/analyze`. `scratch/verify_portable_layouts_browser.mjs` instead marks the live round trip complete when any body text contains OpenCV Evidence, CALIBRATED or UNCALIBRATED. It does not capture the request/response status/body or identify the service. Its programmatic-gate check clicks a disabled button and checks it remains disabled, rather than calling the shared dispatch validation. The required delayed import/response, invalid-file, edit-after-confirmation and keyboard checks are not demonstrated by the reported steps. Do not present these as verified.

After fixing R1/R2, perform the packet's missing browser checks and capture an actual request/response for the target upload after confirmation using the existing endpoint, with service identity, tested revision, status and result tied to submitted ROI IDs. Assert zero analysis requests while unconfirmed. Exercise real save/download/reimport rather than only constructing a layout separately. Distinguish mocked race checks from the unmocked round trip; correct the report's endpoint, schema terminology and completion claims to match observed evidence. If checks cannot run, record them as unmet instead of passed. No backend modification is needed.

## Follow-up

Continue this same task; no separate correction packet or production backend change. Supply corrections in chat for Gemini, rerun affected checks, update implementation evidence and commit locally with this review. No push, PR or merge. Preserve unrelated files and scratch artifacts.

Completion remains manual-region prototype 90–95%, full roadmap 65–75% until this increment is accepted. These are scope estimates, not real-image accuracy. Review and queue changes remain uncommitted.
