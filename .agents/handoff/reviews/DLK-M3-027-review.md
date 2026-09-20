---
task_id: DLK-M3-027
reviewed_commit: ebeacc7d0bb65e42dd4da3c154f43aa0c6adad61
decision: accepted
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-027

## Decision

Accepted after reviewing final correction commit `ebeacc7d0bb65e42dd4da3c154f43aa0c6adad61`. R1–R8 are resolved. The calibrated image workflow now uses shared production validation and request-state transitions that are also executed by the committed dependency-free regression suite.

## Final acceptance review

- R8 resolved: `frontend/lib/image-upload-state.ts` owns the pure configuration validation and request-state transitions. `ImageUpload.tsx` imports and uses these functions, and `frontend/scripts/test-image-upload-state.mjs` imports and executes the same module rather than maintaining a parallel implementation.
- The production ROI boundary tolerance and regression expectation are aligned at `1.00001`.
- All seven regression scenarios passed against the shared production module. Node.js emitted only a non-failing module-type performance warning when loading the TypeScript module.
- Focused ESLint across all 17 task-owned frontend files passed with zero errors and zero warnings.
- The production Next.js build and TypeScript check passed, including all 13 generated routes. The generated `frontend/next-env.d.ts` change was restored.
- Repository-wide ESLint remains at the documented out-of-scope baseline of 16 errors and 10 warnings; no finding is in an R8-owned file.
- Task validation and the committed whitespace check passed.
- No new dependency, backend change, Phase 3 change, raw-image persistence, remote Git operation, or unrelated working-tree file was included.
- Existing unrelated working-tree files remain untouched.

## Second correction review finding

### R8 - P2: Exercise shared production transitions instead of a parallel implementation

`frontend/scripts/test-image-upload-state.mjs:18-220` defines its own `validateAnalysisConfiguration`, `startAnalysis`, `commitSuccess`, `commitError`, `handleReconfigure`, `handleRemove`, and `cleanupController` functions. `frontend/components/diagnosis/ImageUpload.tsx` does not import or call those transition functions. The script can therefore pass while production behavior is broken. It has already drifted: the script accepts ROI boundary sums up to `1.0001`, while production uses `1.00001`, and their validation branches and messages differ.

Extract the pure configuration validation and request-state transitions into one production module used by `ImageUpload.tsx`. Make the runnable regression import and execute that same module. Keep the controller/network orchestration in the component, add no dependency or test framework, and preserve the seven existing scenarios. Because the installed Node.js is v24.11.1, a TypeScript regression entrypoint using Node's type stripping is acceptable if that is the smallest dependency-free design. Update the task packet's allowed paths and implementation report to match the actual shared module and exact runnable command.

## Second correction verification

- Reviewed exact commit `5ba415d7d9c1b0bd1a185d24f7d69cd2adae95d7`; it is local and not pushed.
- R1 resolved: `activeRequestToken` is stored in upload state, result/error updaters atomically check upload existence, configuration revision, and token, and `finally` only cleans the matching controller.
- R5 resolved: the image response contract now documents `Observation.id` and reserves `observation_id` for durable case projections.
- R6 resolved for the touched response models: backend-guaranteed fields are required and nullable fields remain explicit; `ObservationInput` is separated from response `Observation`.
- R7 resolved: ESLint across all 16 changed frontend files passed with zero findings. Repository-wide lint still reports the documented out-of-scope baseline of 16 errors and 10 warnings.
- Task validation and committed whitespace checks passed.
- The committed regression command passed all seven reported scenarios, but those scenarios currently execute duplicate script logic rather than the production transitions.
- The production Next.js build and TypeScript check passed; the generated `frontend/next-env.d.ts` change was restored.
- Existing unrelated working-tree files remain untouched.

## Correction review findings

### R1 - P1: Do not delete the request identity before React commits the result

`frontend/components/diagnosis/ImageUpload.tsx:399-453` schedules a functional `setUploads` update whose callback checks `requestStateRef.current[uploadId]`, then immediately reaches `finally` and deletes that request entry. React may defer the updater callback; when it runs after `finally`, `active?.token` is absent and the valid result or error is silently discarded. The current logic prevents stale commits but does not guarantee that a current analysis can commit.

Store the active request token in the upload state (or otherwise make the state update independent of a ref that `finally` clears). The functional update must atomically confirm upload existence, configuration revision, and request token. Clear the request identity only as part of a design that cannot run before the queued result/error transition. Preserve the existing synchronous invalidation on reconfigure, removal, supersession, and unmount.

The task report says a deterministic state-machine harness passed, but no harness or test is present in the commit. Add a small committed, runnable regression around the extracted request-state transition logic, without introducing a test framework, covering current success, current error, removal, reconfiguration, supersession, and old-finally-versus-new-controller behavior.

### R5 - P2: Use the real image observation identifier in the contract document

`docs/api/frontend-backend-contract.md:89` still says image API `Observation` objects contain `observation_id`. `backend/app/schemas/diagnosis.py:161-171` serializes this field as `id`; `observation_id` is added only by the durable case response projection. Document `id` for `POST /images/analyze` and reserve `observation_id` for `CaseObservationResponse`.

### R6 - P2: Mirror backend-guaranteed response fields as required properties

`frontend/types/api.ts:43-113` and `frontend/types/image.ts:45-81` still mark backend-guaranteed response properties optional. Examples include `CauseEvidence.explanation`, `CandidateCause.missing_evidence` and `score_breakdown`, all `Question` defaults, all `TroubleshootingCheck` defaults, `DiagnosisResult.defect`/`defect_name` property presence, `next_question`, `next_check`, `explanation`, `analysis_revision`, and `warnings`; image response fields such as `channels`, `calibrated_diameter_mm`, `is_missing`, and every aggregate field are also always serialized by the accepted Pydantic response.

Separate request/input types from response types where their optionality differs. Make accepted backend response properties required, using nullable types only where the backend value may be null. Keep truly frontend-only compatibility fields optional and clearly separate.

### R7 - P2: Make the verification report reproducible and accurate

The correction commit adds `questions/page.tsx` and `troubleshooting/page.tsx` to the allowed and changed paths, but the reported focused ESLint command omits both. Running ESLint across every changed frontend source produces 8 errors in those two files. The report's claim that every task-owned file is clean is therefore false. It also reports a deterministic regression harness that is absent from the commit and supplies no runnable command or artifact.

Either keep those integration edits and make both changed files lint-clean, or redesign the type correction so they need no edit and remove them from the correction diff. Commit the small regression harness and record its exact runnable command and output. Update the implementation report with only checks that can be reproduced from the repository.

## Correction review verification

- Reviewed exact correction commit `8f615a6c8e55d2e8519dac319abb0a2bd0d86ce9`; it is local and not pushed.
- Correction commit whitespace inspection passed and the task packet validates.
- Production Next.js build and TypeScript passed; the generated `frontend/next-env.d.ts` change was restored.
- ESLint across every changed frontend source failed with 8 errors, all in the newly task-owned questions and troubleshooting pages.
- No committed test, specification, script, or harness exercises `validateAnalysisConfiguration` or the request-state machine.
- Existing unrelated working-tree changes remain untouched.

## Resolved in correction commit

- R2 resolved: chart bars sum only signed `CauseEvidence.score_contribution` values.
- R3 resolved: finite numeric bounds, ordering, ROI bounds, and positive scale/reference limits are checked before transport.
- R4 resolved: persisted `status`, `coverage_ratio_to_reference`, `current_coverage`, and `reference_coverage` are rendered defensively.

## Original review findings (historical)

### R1 - P1: Make stale-response rejection synchronous and request-specific

`frontend/components/diagnosis/ImageUpload.tsx:160-185, 301-358` checks a completed request against `uploadsRef`, but that ref is updated only in an effect after React commits. A response that settles after removal or reconfiguration but before that effect may still see the old upload and revision, then attach its old calibrated result to the new configuration or recreate a removed entry. The implementation also has no request token, and every request's `finally` unconditionally deletes the controller stored under the upload ID, which can delete a newer request's controller.

Keep a request token/controller identity per upload outside delayed effects. Invalidate it synchronously before aborting on removal or configuration change. Commit a result or error only inside a functional state update that confirms the upload still exists and both its configuration revision and request token match. In `finally`, delete the controller only if the stored controller/token still belongs to that request. Add a deterministic regression or small extracted-state test for reconfigure/remove followed by a late resolution.

### R2 - P1: Plot signed evidence contributions, not the positive penalty summary

`frontend/components/diagnosis/EvidenceGraph.tsx:38-71` prefers `score_breakdown.positive_evidence` and `score_breakdown.contradiction_penalty`. The backend stores `contradiction_penalty` as a positive absolute magnitude, while each contradicting `CauseEvidence.score_contribution` is signed. As a result, contradictory bars point in the positive direction and the chart violates the task requirement to derive both series only from evidence-item contributions with their real signs.

Sum `supporting_evidence[].score_contribution` and `contradicting_evidence[].score_contribution` directly. Do not use `score_breakdown` as the chart source or reverse/absolute the contradictory values. Keep the dynamic score-breakdown table separate.

### R3 - P2: Validate every numeric limit before sending the request

`frontend/components/diagnosis/ImageUpload.tsx:205-299` checks only presence and min/max ordering. The numeric inputs in `ImageCalibrationPanel.tsx` accept state values outside the backend contract because HTML `min`/`max` attributes do not validate this button-driven request. Values such as coverage `1.5`, overflow `-0.1`, reference tolerance `2`, reference minimum `0`, or negative size CV can be sent and rejected only by the backend.

Before calling `imagesApi.analyze`, validate finite numbers and the exact schema ranges: coverage/overflow/presence/tolerance in `[0,1]`, size CV `>= 0`, reference min/max `> 0`, and optional scale `> 0`, in addition to both min/max relationships. Keep the upload ready and show the local per-upload validation message when invalid.

### R4 - P2: Render the persisted image metadata keys that the backend actually stores

`frontend/components/diagnosis/ImageAnalysis.tsx:40-55` reads `reference_ratio`, although reference observations persist `coverage_ratio_to_reference`. It never reads or renders `status`, and therefore misses required persisted status presentation. The component also omits the available reference current/reference coverage basis.

Read and render `status`, `coverage_ratio_to_reference`, `current_coverage`, and `reference_coverage` when present and finite. Continue rendering only proven metadata, with no inferred values.

### R5 - P2: Correct the image contract documentation

`docs/api/frontend-backend-contract.md:69-102` documents an impossible `PROCESSING_FAILED` status and omits the real `UNCALIBRATED` status. It also lists response fields that do not exist, including `roi_index`, `label`, `bounding_box`, `area_pixels`, `deposit_count`, and `DiagnosticObservation.evidence_type/category`; the accepted API returns the names in `backend/app/schemas/image.py`, such as `roi_id`, `deposit_area_px`, `coverage_ratio`, `overflow_ratio`, and ordinary `Observation` fields `source` and `statement_type`.

Rewrite this section directly from the accepted Pydantic schemas and keep the calibrated-evidence rule keyed to `CALIBRATED`, `UNCALIBRATED`, and `UNRELIABLE`.

### R6 - P2: Align touched diagnosis types with backend names and optionality

`frontend/types/api.ts:55-103` still declares fields the backend does not return (`CandidateCause.description`, `base_probability`, candidate `explanation`, question `reasoning`, check `status`, and `defect_confidence`) while requiring `DiagnosisResult.defect` and `defect_name` even though both are nullable. It also omits real check fields such as `priority_score`, `reasoning`, and `possible_outcomes`.

Mirror `CandidateCause`, `Question`, `TroubleshootingCheck`, and `DiagnosisResult` from `backend/app/schemas/diagnosis.py`. Where an old component still needs a display-only compatibility field, make it optional and supply an explicit UI fallback rather than claiming the backend guarantees it.

## Verification

- Exact reviewed commit: `3e222b31241ee56034674d24744780a432bea8e6` on `backend-database`; one local commit ahead of `origin/backend-database` and not pushed.
- Commit path and whitespace inspection passed; all committed paths are authorized by the task.
- Task packet validation: `VALID`.
- Focused ESLint across every task-owned frontend source file: 0 findings.
- Production frontend build: passed under Next.js 16.3.4, including TypeScript and all 13 static pages.
- Repository-wide ESLint: 24 errors and 10 warnings, matching Gemini's report and improving the recorded 42-error/13-warning baseline; all reported findings are outside the task-owned files.
- Build-generated `frontend/next-env.d.ts` change was restored after verification. Existing unrelated working-tree files remain preserved.

## Follow-up

Apply R1-R6 in the same Phase 2 correction, update this task's implementation report and queue state, and create one local correction commit. Do not start Phase 3 and do not perform remote Git operations. Per the user's workflow preference, no separate correction task packet was generated during this review.
