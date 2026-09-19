---
task_id: DLK-M3-026
reviewed_commit: 6e52628f4e6e192a5044dc9de07b0f01b9cdc213
decision: accepted
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-026

## Decision

Accepted at correction commit `6e52628f4e6e192a5044dc9de07b0f01b9cdc213`. All findings R1-R9 are resolved within the approved Phase 1 scope. No blocking findings remain.

## Final correction acceptance

- R8 resolved through the production API: uniform black, mid-gray, and white frames each return HTTP 200 with `status="UNRELIABLE"` and no observations. A synthetic empty target with visible substrate/fiducial context returns `CALIBRATED` with the authorized D04 missing observation.
- R9 resolved: the image API specification now uses only the real `CALIBRATED`, `UNCALIBRATED`, and `UNRELIABLE` statuses; no `UNRELIABLE_REFERENCE` occurrence remains.
- The final commit preserves the accepted R1 and R3-R7 corrections and changes only the task packet, queue, segmentation implementation, synthetic fixture, relevant tests, and image API documentation.
- Reviewer independently ran correction-focused vision, diagnosis/evidence/AI/evaluation, image API, and image-diagnosis checks: 83 passed, 0 failed, 19 warnings.
- Reviewer independently ran the PostgreSQL image workflow and persistence checks against the fail-closed disposable destination: 37 passed, 0 failed, 10 warnings.
- Reviewer independently ran the full backend suite: 466 passed, 0 failed, 41 warnings in 54.93 seconds.
- Task validation and committed whitespace inspection passed. No frontend file, secret, raw image, generated dependency, push, merge, rebase, pull request, or `main` change is part of the reviewed commits.

## Final findings

None.

## Prior correction acceptance evidence

- R1 resolved: an injected internal classifier `ValueError("internal detail C:/private/model/path")` now returns sanitized HTTP 500 and the response contains neither the raw detail nor path.
- R3 resolved: total, inside, and outside areas use exact counts from one selected mask, with a regression asserting `inside + outside == total` and the expected overflow ratio.
- R4 resolved: direct probes with only `max_size_cv` emit no D04; only `min_coverage_ratio` emits D01; only explicit `min_presence_ratio` authorizes D04.
- R5 resolved: both uploads use a bounded chunk reader, an early known-size check, and an unknown-size stream regression that stops after the limit plus one chunk.
- R6 resolved: empty process limits, blank/duplicate ROI IDs, and mode-incompatible limit objects are rejected.
- R7 resolved: benchmark requests once again preserve both scenario description and structured observations, with a capture regression.
- Reviewer independently ran the correction-focused vision, evaluation, image API, and image-diagnosis tests: 54 passed, 0 failed, 19 warnings.
- Gemini reports 461 full backend tests passed. The reviewer did not repeat the full suite because the production API probe below already demonstrates a blocking acceptance failure.

## Prior correction findings R8-R9 (resolved)

### R8 — P1: Treat uniform frames as ambiguous unless the background is established

`backend/app/services/vision/segmentation.py:97-114` assumes that any uniform target and uniform surroundings represent genuine background, regardless of pixel value or an established background model. Through the real image API, completely uniform frames at intensity 0, 64, 128, and 255 all returned HTTP 200, `status="CALIBRATED"`, quality 1.0, and `deposit_presence=missing` when `min_presence_ratio` was supplied. A black/gray uniform frame may be an occluded lens, lighting/camera failure, full-frame material, or otherwise unsegmentable image; the pipeline has no evidence to distinguish those states.

Return `UNRELIABLE` with no observations when target and surroundings are both uniform and no explicit reference/background basis establishes that the frame represents an empty target. Do not use raw brightness as an unstated manufacturing default. Replace the existing plain-white `create_empty_image` proof with a defensible missing-deposit fixture or reference basis, and add API regressions proving uniform dark, mid-gray, and white frames cannot emit score-bearing D04 evidence merely from `min_presence_ratio`.

### R9 — P2: Document the actual reference-mode status enum

`docs/api/api-spec.md:2735` says reference mode may return `status="UNRELIABLE_REFERENCE"`, but `AnalysisStatus` and the actual API define only `CALIBRATED`, `UNCALIBRATED`, and `UNRELIABLE`. A frontend following the documentation can implement an impossible branch and fail to handle the real response.

Replace `UNRELIABLE_REFERENCE` with `UNRELIABLE` and inspect the rest of the image API section for enum consistency.

## Original review evidence and findings

### Original acceptance evidence

- Reviewed exact local commit `82887836a3e38a949a045f667f15bfdad5e4adcf` on `backend-database`; no frontend file, secret, generated dependency, remote Git operation, or raw-image persistence was committed.
- Commit whitespace inspection passed. The DLK-M3-026 task validator remains valid.
- Reviewer independently ran the four focused vision tests: 22 passed.
- Reviewer independently ran diagnosis/evidence/LLM tests: 37 passed.
- Reviewer independently ran image API/diagnosis tests: 13 passed.
- Reviewer independently ran PostgreSQL image-workflow/persistence tests against the repository's fail-closed test destination: 37 passed.
- Reviewer independently ran the full backend suite: 448 passed, 0 failed, 35 warnings in 54.36 seconds.
- Reviewer probes reproduced the seven findings below. Passing counts therefore do not establish the missing acceptance boundaries.

### Original findings R1-R7

### R1 — P1: Treat internal pipeline failures as sanitized 500 responses

`backend/app/api/images.py:159-172` catches every `ValueError` from the complete worker pipeline as a technician-controlled 422 and returns `str(e)`. A mocked internal classifier failure containing `C:/private/model/path` returned HTTP 422 with that exact private detail in the body. This violates the required sanitized unexpected-failure boundary and repeats the error-classification class previously fixed in the case API.

Restrict client-facing 4xx handling to explicit decode/profile/input exceptions with stable sanitized messages. Let unexpected internal `ValueError` and other implementation failures reach the logged, sanitized 500 handler. Add a regression that injects an internal worker/classifier `ValueError`, asserts 500, asserts the raw detail/path is absent, and retains ordinary invalid-profile/image 4xx coverage.

### R2 — P1: Do not infer “missing” from a uniform target crop

`backend/app/services/vision/segmentation.py:73-98` labels every low-variance target crop as a reliable missing deposit before comparing it with the surrounding analysis window. A 100x100 white image with a clearly visible solid black 40x40 deposit exactly filling the target returned `SUCCESS`, `is_missing=True`, zero area, and quality 1.0. The same implementation also only penalizes a border-touching candidate at lines 210-218 and never compares the best two candidates for ambiguity, despite the task requiring border-dominant and indistinguishably ambiguous masks to be rejected.

Use target-to-surrounding contrast before deciding missing versus filled, and return `UNRELIABLE` when polarity/background cannot be distinguished. Reject or downgrade clipped/border-dominant and near-tied candidates rather than returning calibrated measurements. Add regressions for uniform background, uniform deposit inside a contrasting window, a clipped border candidate, and two similarly plausible candidates.

### R3 — P1: Calculate pixel ratios from one consistent mask basis

`backend/app/services/vision/segmentation.py:141-151` stores contour geometry area as total deposit area but counts pixels for inside-target area, then lines 185-195 subtract those incompatible quantities. A radius-25 synthetic deposit produced contour total 1,886, inside pixels 1,559, reported outside 327, while the selected mask contained 1,957 pixels and therefore 398 outside pixels. Overflow was understated by about 18 percent. This can suppress D05 evidence near the caller's limit and makes the documented pixel formulas false.

Derive total, inside, and outside deposit pixels from the same binary mask. Keep contour area separately only for contour-derived shape metrics if needed. Add an exact mask-count regression for a deposit crossing the ROI boundary and assert `inside + outside == total` plus the expected overflow ratio.

### R4 — P1: Emit only the evidence dimension explicitly authorized by the caller

`backend/app/services/vision/defect_classifier.py:72-88` always converts `m.is_missing` or zero deposit area into D04, even when `min_presence_ratio` was not supplied. A direct call with only `ProcessLimits(max_size_cv=0.2)` returned `CALIBRATED` plus `deposit_presence=missing`. The committed D04 integration test also supplies only `min_coverage_ratio` but expects a presence observation, so it currently codifies the task-contract violation.

Gate D04 strictly on an explicit presence limit. With only a coverage limit, zero coverage may produce the corresponding size comparison, but it must not silently switch evidence dimensions. Add negative tests for every omitted limit and update the D04 test to supply `min_presence_ratio`.

### R5 — P2: Enforce the 10 MB boundary without reading an arbitrary upload into memory

`backend/app/api/images.py:142-157` calls `await file.read()` and `await reference_file.read()` with no size before checking length. The implementation report calls this a streaming-level limit, but a very large request is fully materialized in application memory first. No middleware or other body limit exists in the backend.

Use the trusted upload size when present for an early rejection and still read in bounded chunks up to 10 MB plus one byte so chunked or missing-length uploads cannot bypass the limit. Apply the same behavior to the reference file and test the bounded-read path rather than only posting an 11 MB in-memory byte string.

### R6 — P2: Reject ambiguous and mode-incompatible analysis profiles

`backend/app/schemas/image.py:62-127` accepts an empty `process_limits` object, simultaneous process and reference limits, and duplicate `roi_id` values. The first can return `CALIBRATED` with no comparison basis; the second silently ignores caller input; the third makes reference pairing and missing-ROI metadata ambiguous. These are the incompatible values the task requires the API to reject.

Require at least one process limit in `PROCESS_LIMITS`, reject limit objects that do not belong to the selected mode, and require unique nonblank ROI IDs. Add schema/API 422 regressions for each case and document the rules.

### R7 — P2: Keep the benchmark on the real mixed-evidence intake contract

`backend/app/evaluation/benchmark.py:66-69` was outside the task's allowed paths and now erases every scenario description whenever structured observations exist. Production intentionally merges those two evidence sources, so the benchmark no longer exercises the behavior it claims to evaluate and can hide extraction or duplicate-evidence regressions.

Revert the description suppression. If benchmark expectations change because the new production contract is correct, update the relevant benchmark scenarios or assertions transparently and add a regression proving a scenario with both inputs reaches the engine with both inputs intact.

## Follow-up

DLK-M3-026 is accepted. Phase 2 planning is the next programme dependency when requested; no next task packet was generated during this review. Remote Git operations remain unauthorized until the user explicitly requests them.
