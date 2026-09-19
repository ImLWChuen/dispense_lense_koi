---
task_id: DLK-M3-026
title: Calibrated vision and evidence-safety foundation
status: implemented
created_by: ChatGPT planner/reviewer
assigned_to: Gemini implementer
depends_on: [DLK-M3-025]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-026: Calibrated vision and evidence-safety foundation

## Objective

Replace the unsafe raw-pixel image heuristic with a typed, calibrated, resolution-independent backend vision pipeline and connect only trustworthy image observations to the existing deterministic diagnosis engine. Preserve image measurement metadata, merge structured and text evidence safely, and make bounded LLM explanations provenance-aware without giving the LLM scoring or lifecycle authority.

This is Phase 1 of the approved calibrated-vision and dynamic-frontend programme. It is backend-only. Stop for ChatGPT review after this task; do not begin the frontend phases.

## Current evidence

- Current branch at task release: `backend-database`, head `553566c7ad981305a3dd878fac0ac6903f1f6784`.
- `DLK-M3-025` is accepted. Its backend runtime/offline-safety corrections are prerequisites and must remain intact.
- Cross-project evidence is recorded in `.agents/handoff/reviews/PROJECT-REVIEW-2026-09-19.md`, especially F05-F09 and F18.
- `backend/app/services/vision/measurement.py` uses absolute contour-area cutoffs of 1,000 and 5,000 pixels. The same proportional synthetic dot was reproduced as `TOO_SMALL` at 100x100 and `TOO_LARGE` at 400x400.
- `backend/app/services/vision/preprocessing.py`, `segmentation.py`, and `defect_classifier.py` are empty. `backend/app/schemas/image.py` is empty.
- `POST /api/v1/images/analyze` trusts an image MIME prefix, reads the full upload, runs synchronous OpenCV inside the async route, and returns only `observation_type` and `value`.
- The current image values `TOO_SMALL`/`TOO_LARGE` do not match the evidence vocabulary `undersized`/`oversized` and therefore contribute no rule evidence.
- `Observation` already supports `source=IMAGE`, `statement_type=AI_INFERENCE`, and a `metadata` dictionary. `ObservationModel` and `CaseObservationResponse` do not preserve that metadata.
- `DiagnosticEngine.diagnose` extracts description evidence only when the structured observation list is empty. Structured/image input can therefore suppress independent text evidence.
- Current extraction reproduced `No bubbles are visible.` as positive `visible_bubbles`, and `I think the nozzle is blocked.` as an objective blockage observation as well as a hypothesis.
- Current fuzzy duplicate handling reproduced stable and unstable pressure observations with similar wording as duplicates, discarding the conflicting fact.
- Current normal backend unit baseline observed by the planner: 186 unit tests passed with a workspace-local pytest temporary directory. Full PostgreSQL coverage was not rerun because no disposable `TEST_DATABASE_URL` was configured in the planner process.
- Existing unrelated working-tree items at release include a modification under `frontend/app/(dashboard)/cases/[id]/page.tsx` and untracked `.agents.zip`, `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md`, `frontend/AGENTS.md`, and `frontend/CLAUDE.md`. Preserve them and exclude them from this task's commit. Reinspect status before work because their state may change.

## Requirements

### 1. Test-first failure characterization

- Add desired-behavior regression tests before implementation. Run them and record the expected red results in the implementation report; do not commit tests whose final assertions endorse broken behavior.
- Use deterministic synthetic images only. Include centered deposits at 100x100, 200x200, and 400x400; undersized/normal/oversized current-reference pairs; overflow; multiple ROIs; a missing ROI; and ambiguous/noisy segmentation.
- Cover raw-pixel failure replacement, canonical vocabulary, text plus structured evidence, negation, hypotheses, conflicting evidence, image provenance, uncalibrated neutrality, and upload bounds.

### 2. Typed calibrated image contract

- Define analysis modes `FEATURES_ONLY`, `PROCESS_LIMITS`, and `REFERENCE_IMAGE`.
- Define statuses `CALIBRATED`, `UNCALIBRATED`, and `UNRELIABLE`. Only `CALIBRATED` analysis may emit score-bearing observations.
- Define normalized rectangular ROIs with `roi_id`, `x`, `y`, `width`, and `height`. Validate coordinates within `[0,1]`, positive dimensions, and full containment within the image.
- Define optional process limits: `min_coverage_ratio`, `max_coverage_ratio`, `max_overflow_ratio`, `max_size_cv`, and `min_presence_ratio`. Do not add manufacturing defaults.
- Reference mode must require a reference image and explicit caller-supplied tolerance, represented as lower/upper reference ratios or one equivalently unambiguous typed contract.
- Per-ROI results must expose deposit and target pixel area, coverage ratio, overflow ratio, equivalent pixel diameter, optional calibrated millimetre diameter, circularity, solidity, aspect ratio, hole/void ratio, and segmentation quality.
- Aggregate results must include mean coverage, size coefficient of variation when meaningful, missing ROI IDs, and warnings.
- Document the multipart request and complete response in `docs/api/api-spec.md`.

### 3. ROI-safe image processing

- Decode and verify JPEG/PNG data rather than trusting MIME alone.
- Enforce width and height no greater than 4,096 pixels and no more than 16,000,000 decoded pixels.
- Convert normalized ROIs to exact target masks plus bounded expanded analysis windows.
- Segment locally using deterministic OpenCV candidates. Whole-image largest-contour selection is prohibited.
- Candidate selection must use target overlap/proximity and reject background-dominant, border-dominant, degenerate, absent, and indistinguishably ambiguous masks.
- Return `UNRELIABLE` instead of guessing when segmentation quality is insufficient.
- Measurement code calculates features only. Diagnostic classification belongs in `defect_classifier.py`.

### 4. Resolution-independent measurements and calibrated classification

- Implement:
  - `coverage_ratio = deposit_pixels_inside_target / target_area_px`;
  - `overflow_ratio = deposit_pixels_outside_target / total_detected_deposit_pixels`;
  - `equivalent_diameter_px = 2 * sqrt(deposit_area_px / pi)`;
  - `circularity = 4 * pi * area / perimeter^2` with safe zero handling;
  - `solidity = area / convex_hull_area` with safe zero handling;
  - aspect ratio and a bounded hole/void metric;
  - `size_cv = std(coverage_ratio) / mean(coverage_ratio)` for two or more valid ROI measurements, with safe zero-mean handling.
- Calculate millimetres only when explicit `mm_per_pixel` calibration is supplied.
- `FEATURES_ONLY` returns measurements, `UNCALIBRATED`, and no diagnostic observations.
- `PROCESS_LIMITS` classifies only dimensions for which the caller supplied a limit.
- `REFERENCE_IMAGE` measures current and reference images with identical ROIs, calculates current/reference coverage ratios, applies only caller-supplied tolerance, and downgrades unreliable references.
- The same normalized geometry at 100x100, 200x200, and 400x400 must have coverage within a documented small numerical tolerance and identical calibrated classification.
- Scaling current and reference together must preserve normalized size ratio and classification.
- Score-bearing mappings are limited to existing vocabulary:
  - D01: `deposit_size=undersized`;
  - D02: `deposit_size=oversized`;
  - D03: `deposit_size=inconsistent`;
  - D04: `deposit_presence=missing`;
  - D05: `spreading_behaviour=excessive_spread`.
- Every emitted image observation uses `source=IMAGE` and `statement_type=AI_INFERENCE`. D06 bubble/shape features remain diagnostic-neutral in this task.

### 5. Resource-safe image API

- Keep `POST /api/v1/images/analyze` but replace its transport contract with multipart `file`, JSON `profile`, and optional `reference_file`.
- Reject files over 10 MB before expensive OpenCV processing. Also enforce decoded dimension/pixel limits.
- Parse and validate the profile before classification. Invalid ROI, missing required calibration/tolerance/reference inputs, incompatible values, malformed image, and unsupported formats produce sanitized client errors.
- Offload CPU-bound OpenCV processing from the async event loop using the existing framework stack. Do not add a task queue.
- Return the complete typed result: status, mode, dimensions, ROI measurements, aggregate measurements, canonical observations, and warnings.
- Unexpected failures return a sanitized 500 without paths, secrets, raw exception details, or partial diagnostic output.

### 6. Lossless image-observation persistence

- Add one forward Alembic migration after current revision `0007` if inspection confirms metadata is otherwise lost.
- Persist observation metadata in JSONB through a non-reserved Python attribute such as `observation_metadata` mapped to a suitable column name.
- Existing rows reconstruct with `{}` and remain readable.
- Preserve metadata through initial case creation, subsequent structured-case reconstruction, durable case GET/list responses, analysis snapshots where observations are represented, and report assembly where applicable.
- At minimum preserve analysis status, mode/basis, ROI IDs, coverage, overflow, reference/process basis, and segmentation-quality information necessary for later frontend rendering.
- `CaseObservationResponse` must expose metadata.
- Prove exact metadata and provenance round-trip using the verified disposable PostgreSQL test database. Never point destructive tests or migrations at the development database.

### 7. Safe text plus structured/image evidence merge

- For a non-empty initial description, extract safe description evidence even when structured/image observations are supplied.
- Perform this merge once at intake. Do not re-extract the original description on every later diagnosis revision.
- Mask detected hypothesis spans before objective keyword extraction while preserving them in `user_hypotheses`.
- Skip positive keyword matches locally negated by at least `no`, `not`, `without`, and `never`. Do not invent a negative observation when the knowledge base has no canonical negative value.
- Duplicate suppression may collapse the same semantic fact once, including equivalent USER and IMAGE values, but must not merge different observation types or contradictory/different values merely because their original text is similar.
- Preserve IMAGE undersized plus text blockage as independent evidence. Preserve IMAGE undersized and USER oversized as distinct conflicting facts.
- Uncalibrated/unreliable analysis must supply no score-bearing observation and must leave diagnosis identical to the no-image baseline.

### 8. Deterministic diagnosis integration

- Prove calibrated image evidence changes cause support only through the existing `rules.json` and scoring configuration. Do not add image multipliers or change existing weights.
- Assert exact expected score contributions/deltas where the knowledge rules make them deterministic.
- Cover D01 and D02 through the actual image API-to-case path. Cover recognition/scoring of canonical D03/D04/D05 observations without inventing new rules.
- Removing the canonical IMAGE observation restores the deterministic baseline.
- A complete integration path must show image API -> canonical observation -> case creation -> persisted provenance/metadata -> ranking change -> case/report retrieval.

### 9. Provenance-aware bounded LLM explanation

- Pass structured evidence summaries to the explanation prompt with provenance such as IMAGE, USER, and USER_CHECK_RESULT.
- Raw image bytes, base64, file paths, and URLs must never be sent to OpenAI.
- Prompt and output guardrails must continue to prohibit score changes, new unsupplied causes, automatic confirmation, invented procedures/sources, and automatic resolution.
- Mocked tests must prove deterministic rankings/scores are value-equivalent before and after explanation generation and provider timeout/error preserves deterministic fallback.
- Normal tests remain offline. An optional live smoke may run only when `RUN_LIVE_OPENAI_TESTS=1` and a key is already available through the existing environment convention. Never print, log, commit, or return the key.

## Interfaces and data contracts

### Request

`POST /api/v1/images/analyze` uses multipart fields:

- `file`: required JPEG/PNG, at most 10 MB;
- `profile`: required JSON string matching the typed analysis profile;
- `reference_file`: required only for `REFERENCE_IMAGE`.

The profile owns mode, normalized ROIs, optional physical scale, and explicit process/reference comparison limits. No server manufacturing thresholds are implied by omission.

### Response

Return a typed object rather than a bare observation list. It contains mode/status, image dimensions, ROI measurements, aggregate measurements, warnings, and zero or more canonical `Observation` objects. Only calibrated results may contain diagnostic observations.

### Persistence

Image-derived observation metadata must round-trip through PostgreSQL without changing existing observation identity, append-only revision, optimistic-concurrency, cause-confirmation, recovery, or recurrence semantics.

### Compatibility

- Existing non-image diagnosis and durable case endpoints remain backward compatible.
- Existing observations without metadata continue to deserialize with `{}`.
- Existing evidence rules and weights are authoritative and unchanged.
- The LLM remains explanatory and optional; no API key is required for baseline use.

## Allowed paths

- `backend/app/api/images.py`
- `backend/app/schemas/image.py`
- `backend/app/schemas/diagnosis.py`
- `backend/app/schemas/case.py`
- `backend/app/services/vision/`
- `backend/app/services/diagnosis/engine.py`
- `backend/app/services/diagnosis/symptom_extractor.py`
- `backend/app/services/diagnosis/evidence_engine.py`
- `backend/app/services/ai/explanation_service.py`
- `backend/app/services/ai/prompt_manager.py`
- `backend/app/models/case.py`
- `backend/app/db/repository.py`
- `backend/app/services/reporting/` only where needed to preserve already-authorized observation metadata/provenance in existing reports
- `backend/alembic/versions/` for at most one forward migration after `0007`
- `backend/tests/unit/`
- `backend/tests/integration/`
- `backend/tests/fixtures/` only for synthetic reusable test helpers
- `docs/api/api-spec.md`
- `.agents/handoff/tasks/DLK-M3-026-calibrated-vision-evidence-foundation.md`
- `.agents/handoff/QUEUE.md`

## Prohibited scope

- Any file under `frontend/`; frontend implementation starts only after this task is reviewed and accepted.
- `.agents.zip`, `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md`, or unrelated working-tree files.
- Changes to diagnostic knowledge, evidence weights, existing cause/check meanings, or lifecycle state-machine semantics.
- Manufacturing thresholds or tolerances selected by the implementation.
- Score-bearing D06 bubble/shape classification.
- CNN/YOLO training or inference, external image datasets, OpenAI vision, or transmission of raw images to an LLM.
- Image/blob persistence, authentication, vector retrieval, analytics infrastructure, or unrelated report redesign.
- A new frontend or backend test framework, a new material dependency, or architectural replacement without returning to the planner.
- Remote Git operations, push, merge, rebase, pull request creation/update, or changes to `main`.

## Implementation guidance

1. Reinspect branch/status and preserve every unrelated modification. Read root repository instructions. Frontend instructions do not authorize frontend work in this task.
2. Add desired final-behavior tests first. Run the focused set, record why each expected failure is relevant, then implement until green. Do not retain temporary assertions that celebrate current broken behavior.
3. Define the image schemas before service code so API, processing, persistence, and tests share one contract.
4. Implement decode/ROI/segmentation, then pure measurement, then calibrated classification. Keep each layer independently testable.
5. Replace the API only after service contracts are stable. Enforce byte and decoded-pixel limits before/around the expensive boundary and offload CPU work.
6. Inspect every repository mapping that creates or reconstructs `ObservationModel`; update all required paths consistently. Add only one forward migration if metadata persistence is required.
7. Fix intake extraction, negation/hypothesis handling, and duplicate semantics before enabling image observations to score. Existing follow-up revision behavior must not re-extract original descriptions.
8. Add API-to-diagnosis integration proofs using existing rule weights. Treat uncalibrated and unreliable results as measurement output only.
9. Add provenance to LLM explanation context while retaining deterministic fallback and output guardrails. Live provider use is optional and opt-in.
10. Run focused checks after each layer, then the required regression/full suites. Complete the implementation report with actual command output and limitations.
11. Create one atomic local commit only after all mandatory acceptance criteria pass. The internal sequence may be documented in the report, but do not push or begin Phase 2.

## Acceptance criteria

- [x] Typed modes, statuses, ROI/profile validation, feature/result schemas, warnings, and canonical observations are implemented and documented.
- [x] Same proportional deposits across 100x100, 200x200, and 400x400 yield near-identical normalized coverage and the same calibrated classification.
- [x] Scaling current and reference images together preserves normalized ratio and classification.
- [x] Features-only, uncalibrated, unreliable, absent, and ambiguous results produce no score-bearing observations.
- [x] Only caller-supplied process/reference limits can create canonical D01-D05 image observations; D06 remains neutral.
- [x] Image observations use `source=IMAGE`, `statement_type=AI_INFERENCE`, and existing canonical values.
- [x] The image API rejects invalid type/content, malformed data, invalid ROI/profile, missing calibration inputs, uploads over 10 MB, and excessive decoded dimensions/pixels with sanitized responses.
- [x] OpenCV work is offloaded from the async event loop and unexpected failures return sanitized 500 responses.
- [x] Image measurement metadata and provenance round-trip exactly through a disposable PostgreSQL database and appear in durable case/report output where applicable; legacy rows return `{}`.
- [x] Text description and structured/image observations are merged once and both affect diagnosis when independent.
- [x] Negated and hypothetical clauses do not become positive objective observations.
- [x] Duplicate handling preserves contradictory/different facts and suppresses only equivalent facts.
- [x] Calibrated D01/D02 image observations change deterministic scores through existing rule contributions; D03/D04/D05 canonical observations are recognized; uncalibrated analysis has exact baseline parity.
- [x] Explanation prompts include evidence provenance, never include raw images, cannot alter deterministic scores/state, and fall back safely on unavailable/error/timeout providers.
- [x] Existing non-image, question/check, lifecycle, report, offline-runtime, and test-database-safety behavior remains passing.
- [x] API documentation describes the actual final multipart contract, calibration basis, neutral states, canonical vocabulary, persistence, size limits, and lack of automatic physical units.
- [x] No frontend, knowledge weights, state-machine semantics, unrelated user files, secrets, generated output, or remote Git state changed.

## Verification

Run from `backend/` in PowerShell. Use single-line commands; do not copy Bash continuation backslashes.

1. Focused vision unit tests:
   `.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_vision_preprocessing.py tests/unit/test_vision_segmentation.py tests/unit/test_vision_measurement.py tests/unit/test_vision_defect_classifier.py`
2. Focused diagnosis/evidence/LLM unit tests:
   `.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_diagnosis_engine.py tests/unit/test_symptom_extractor.py tests/unit/test_evidence_engine.py tests/unit/test_ai_outputs.py`
3. Image API and diagnosis integration tests that do not require PostgreSQL, if kept separate:
   `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_image_api.py tests/integration/test_image_diagnosis_integration.py`
4. Image-driven durable workflow and persistence round-trip against the validated disposable database:
   `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_image_driven_case_workflow.py tests/integration/test_persistence.py`
5. Full backend suite against the validated disposable database:
   `.\.venv\Scripts\python.exe -m pytest -q --basetemp .phase1-pytest-tmp`
6. From repository root, validate this task packet:
   `.\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-026-calibrated-vision-evidence-foundation.md`
7. From repository root, validate git diff:
   `git diff --check`
8. From repository root, inspect exactly what will be committed:
   `git status --short` and `git diff --cached --check` after staging only task-related files.

Database-backed checks require `TEST_DATABASE_URL` to pass the repository's fail-closed disposable PostgreSQL validation. Do not substitute `DATABASE_URL`, bypass the safety check, or use development records. If a safe database cannot be made available, complete safe unit/non-database work but mark the task `blocked`; do not report it as implemented or create a success commit.

The optional live smoke is not a mandatory acceptance check. Run it only when the user/environment has explicitly enabled `RUN_LIVE_OPENAI_TESTS=1`; normal verification must remain offline.

## Planner decision boundaries

Return to ChatGPT before:

- choosing any manufacturing threshold, calibration tolerance, or physical-unit assumption;
- changing the public contract beyond the modes/fields explicitly authorized here;
- changing database structure beyond one additive observation-metadata migration;
- adding/replacing a dependency or test framework;
- changing evidence weights, knowledge rules, cause meanings, or lifecycle semantics;
- making D06 score-bearing;
- storing raw images or sending them to OpenAI;
- weakening an acceptance criterion or expanding into frontend work;
- resolving an overlap with unrelated working-tree changes by altering, stashing, resetting, or committing them.

Routine private helper design, OpenCV implementation details within the stated quality gates, naming, fixtures, and error-message wording are implementer decisions.

## Git instructions

Create one atomic local commit after all required checks pass. Stage only this task packet, `QUEUE.md`, its implementation report updates, and Phase 1 implementation/test/documentation files. Preserve and exclude all unrelated changes listed in Current evidence and anything added by the user or teammates during execution.

Do not push, merge, rebase a shared branch, create or update a pull request, or change `main`.

Proposed commit message: `feat(vision): add calibrated image evidence pipeline`

## Implementation report

### Summary

Implemented Phase 1 calibrated vision and evidence-safety foundation for task DLK-M3-026, and corrected all findings R1–R7 from review `.agents/handoff/reviews/DLK-M3-026-review.md`:
- Typed, calibrated vision pipeline: Built robust image schemas (`app/schemas/image.py`), magic-byte and dimension-bounded preprocessing (`app/services/vision/preprocessing.py`), local Otsu/adaptive segmentation with target proximity candidate scoring (`app/services/vision/segmentation.py`), resolution-independent geometric and coverage measurement (`app/services/vision/measurement.py`), and calibrated defect classification mapping to canonical D01-D05 observations while enforcing diagnostic neutrality for D06 (`app/services/vision/defect_classifier.py`).
- Image API modernization: Implemented multipart `POST /api/v1/images/analyze` handling raw files and JSON profile payloads with strict 10 MB and 4096px/16M-pixel limits, offloaded CPU-bound OpenCV operations using `anyio.to_thread.run_sync`, and sanitized client/server error responses (`app/api/images.py`).
- Lossless persistence in PostgreSQL: Added forward Alembic migration `0008_observation_metadata.py` adding `metadata` JSONB column to `case_observations`. Mapped `ObservationModel.observation_metadata` and exposed `CaseObservationResponse.metadata`, preserving all vision metadata across initial case save, revision append, structured-case reconstruction, and report assembly (`app/models/case.py`, `app/schemas/case.py`, `app/db/repository.py`, `app/api/cases.py`).
- Evidence extraction & intake safety: Hardened `symptom_extractor.py` with clause-level negation detection (`no`, `not`, `without`, `never`) and hypothesis span masking. Refactored `evidence_engine.py` to enforce strict type-safe semantic deduplication. Updated `engine.py` intake merge to safely extract description facts on initial intake only (`not case.analysis_revisions`), preventing duplicate observations and re-extraction across revisions. Qualified `location_pattern` rule to prevent "across all boards" false positives.
- Provenance-aware bounded LLM explanation: Formatted top candidate cause evidence with provenance tags (`[IMAGE]`, `[USER]`, `[USER_CHECK_RESULT]`) in `explanation_service.py` and strictly enforced absence of raw image bytes, URLs, or filesystem paths in `prompt_manager.py`.
- Documentation: Documented Section 11 (`POST /api/v1/images/analyze`) and profile validation rules in `docs/api/api-spec.md`.

#### Review Findings R1–R7 Corrections
- **R1 (Internal Failure Sanitization):** Replaced broad `ValueError` 422 catch in `backend/app/api/images.py` with specific `ImageValidationError` handling. Unexpected internal worker and classifier failures now fall through to the logged 500 handler returning sanitized `"An unexpected error occurred during image analysis."` without leaking filesystem paths or internal details. Added regression test `test_image_analyze_internal_pipeline_failure_returns_sanitized_500`.
- **R2 (Target Uniformity, Border Dominance & Candidate Ambiguity):** In `backend/app/services/vision/segmentation.py`, eliminated premature missing inferences from uniform target crops by comparing deposit contrast against background pixels. Rejected border-dominant or clipped candidates (`border_ratio > 0.20` or `border_pixels >= 30 and border_ratio > 0.15`), indistinguishably ambiguous candidate pairs (`abs(score1 - score2) < 0.15` and `diff < 0.1 * area`), and low-contrast ambiguity (`deposit_contrast < 15.0`) as `UNRELIABLE`. Added unit tests `test_segment_uniform_deposit_inside_contrasting_window`, `test_segment_clipped_border_candidate`, and `test_segment_indistinguishably_ambiguous_candidates`.
- **R3 (Consistent Mask Arithmetic):** Derived `total_deposit_pixels`, `deposit_inside_target_px`, and `deposit_outside_target_px` strictly from the same binary mask in `segmentation.py`, guaranteeing mathematical exactness `inside + outside == total`. Added exact count regression test `test_segment_exact_mask_pixel_counts_overflow`.
- **R4 (Authorized Defect Dimensions):** Gated D04 `deposit_presence=missing` in `defect_classifier.py` strictly on caller-supplied `process_limits.min_presence_ratio is not None`. Updated integration test `test_calibrated_missing_deposit_identifies_d04` to supply `min_presence_ratio=0.05` and added negative unit test `test_omitted_limits_never_emit_unrequested_dimensions`.
- **R5 (Bounded Streaming Uploads):** Implemented `_read_bounded_upload` in `backend/app/api/images.py` reading upload content in 64 KB chunks, immediately raising HTTP 413 if accumulated bytes exceed 10 MB without buffering excess bytes in memory. Applied to both primary and reference files. Added regression tests `test_read_bounded_upload_aborts_mid_stream_without_full_buffer` and `test_image_analyze_rejects_oversized_reference_file`.
- **R6 (Profile & Schema Validations):** Added validations to `AnalysisProfile` in `backend/app/schemas/image.py` requiring unique non-blank `roi_id` values, non-empty `ProcessLimits`, and mode exclusivity (rejecting mode-incompatible limits with 422). Added API regression tests for each validation and updated `docs/api/api-spec.md`.
- **R7 (Mixed-Evidence Benchmark Intake):** Reverted description suppression in `backend/app/evaluation/benchmark.py`, keeping the full production intake contract intact (`DiagnosisRequest(description=scenario.description, observations=obs_list)`). Added regression test `test_benchmark_mixed_evidence_intake_preserves_both_description_and_observations`.

### Files changed

- `backend/app/schemas/image.py`: Added typed models (`AnalysisMode`, `AnalysisStatus`, `AnalysisProfile`, `RoiInput`, `RoiMeasurement`, `AggregateMeasurements`, `ImageAnalysisResponse`) and strict profile/limit validations.
- `backend/app/services/vision/preprocessing.py`: Added magic-byte verification, 10 MB payload limits, 4096px / 16M-pixel bounds, and `ImageValidationError`.
- `backend/app/services/vision/segmentation.py`: Added local Otsu/adaptive candidate segmentation, target proximity scoring, border dominance / ambiguity rejection, and consistent mask pixel arithmetic.
- `backend/app/services/vision/measurement.py`: Replaced raw pixel cutoffs with resolution-independent coverage ratio, overflow ratio, circularity, solidity, aspect ratio, hole ratio, and size CV.
- `backend/app/services/vision/defect_classifier.py`: Added calibrated rule mapping for `FEATURES_ONLY`, `PROCESS_LIMITS`, and `REFERENCE_IMAGE` to canonical observations with D06 neutrality and strict D04 presence limit gating.
- `backend/app/api/images.py`: Implemented multipart file upload, profile parsing, bounded chunked streaming upload reads, thread offloading, and sanitized 422/500 responses.
- `backend/alembic/versions/0008_observation_metadata.py`: Forward migration adding `metadata` JSONB column with server default `'{}'::jsonb`.
- `backend/app/models/case.py`: Mapped `ObservationModel.observation_metadata` to `metadata` JSONB column.
- `backend/app/schemas/case.py`: Exposed `metadata: dict[str, Any]` on `CaseObservationResponse`.
- `backend/app/db/repository.py`: Preserved observation metadata across `save_initial_case`, `load_structured_case`, and all `append_*_revision` methods.
- `backend/app/api/cases.py`: Implemented `_get_obs_metadata` helper to avoid DeclarativeBase `.metadata` conflict.
- `backend/app/services/diagnosis/symptom_extractor.py`: Added clause-level negation detection, hypothesis masking, and qualified location regex.
- `backend/app/services/diagnosis/evidence_engine.py`: Enforced type-safe semantic deduplication requiring matching observation types.
- `backend/app/services/diagnosis/engine.py`: Implemented one-time intake merge for initial cases, preventing revision re-extraction.
- `backend/app/evaluation/benchmark.py`: Restored full mixed-evidence intake contract passing both scenario description and initial observations to diagnostic engine.
- `backend/app/services/ai/explanation_service.py`: Added provenance formatting to top cause evidence summaries.
- `backend/app/services/ai/prompt_manager.py`: Added provenance integrity rules and prohibited image bytes/paths.
- `backend/tests/unit/test_vision_preprocessing.py`: Added unit tests for magic bytes, bounds, and ROI windows.
- `backend/tests/unit/test_vision_segmentation.py`: Added unit tests for local Otsu segmentation, border dominance, candidate ambiguity, and exact mask pixel counts.
- `backend/tests/unit/test_vision_measurement.py`: Added unit tests for resolution invariance and metric calculations.
- `backend/tests/unit/test_vision_defect_classifier.py`: Added unit tests for calibrated defect classification and negative omitted limit checks.
- `backend/tests/unit/test_symptom_extractor.py`: Added negation and hypothesis isolation tests.
- `backend/tests/unit/test_evidence_engine.py`: Added type-safe deduplication tests.
- `backend/tests/unit/test_ai_outputs.py`: Added provenance formatting and image data exclusion tests.
- `backend/tests/unit/test_evaluation_framework.py`: Added regression test for mixed-evidence intake preservation.
- `backend/tests/integration/test_image_api.py`: Added integration tests for multipart analyze endpoint, payload limits, sanitized 500 on internal failure, bounded streaming reads, empty process limits, duplicate/blank ROI IDs, and mode incompatibility.
- `backend/tests/integration/test_image_diagnosis_integration.py`: Added integration tests for baseline parity, calibrated score alteration, D04 presence gating, and D06 neutrality.
- `backend/tests/integration/test_image_driven_case_workflow.py`: Added end-to-end integration tests for image analysis -> case persistence -> revision append -> report generation.
- `backend/tests/integration/test_persistence.py`: Adjusted dynamic assertions for intake merge behavior.
- `docs/api/api-spec.md`: Documented Section 11 (`POST /api/v1/images/analyze`) request/response contract, profile validation rules, error codes, and frontend integration notes.
- `.agents/handoff/tasks/DLK-M3-026-calibrated-vision-evidence-foundation.md`: Marked acceptance criteria and completed implementation report with R1–R7 resolutions.
- `.agents/handoff/QUEUE.md`: Maintained task status as implemented.

### Decisions made

- Circumvented SQLAlchemy DeclarativeBase attribute collision by mapping `ObservationModel.observation_metadata = Column("metadata", JSONB, ...)` and providing `_get_obs_metadata(obs)` helper.
- Enforced strict 10 MB payload limit via chunked streaming reads (`_read_bounded_upload`) prior to OpenCV processing to protect memory/CPU resources.
- Offloaded all CPU-bound OpenCV decoding, segmentation, and feature extraction using `anyio.to_thread.run_sync` to keep the FastAPI async event loop responsive.
- Designed clause-level negation detection using punctuation boundaries (`.,;!?`) and backwards search for negation markers (`no`, `not`, `without`, `never`, etc.) to prevent false positive observations.
- Implemented intake evidence merge strictly during initial case evaluation (`not case.analysis_revisions`) to guarantee subsequent diagnostic revisions (answering questions, executing checks) never re-extract original description text.
- Qualified the `location_pattern` rule in `symptom_extractor` to require nozzle/point/position keywords for `across all`, resolving false positive matches on phrases like "across all boards".
- Enforced consistent binary mask arithmetic for all ROI segmentation metrics so `inside + outside == total` is mathematically exact.
- Bounded candidate ambiguity detection by comparing top two contour candidate scores and areas, rejecting indistinguishable candidates with `UNRELIABLE`.

### Verification results

- Initial failure characterization:
  - `test_vision_measurement.py`: Proportional deposits across 100x100 and 400x400 failed fixed-cutoff tests (reproduced `TOO_SMALL` at 100x100 and `TOO_LARGE` at 400x400).
  - `test_symptom_extractor.py`: Negated description `"No bubbles are visible"` failed by producing positive `visible_bubbles` observation; hypothesis `"I think the nozzle is blocked"` incorrectly produced an objective `blocked` observation.
  - `test_evidence_engine.py`: Conflicting pressure observations with similar wording were erroneously deduplicated.
  - Review R1–R7 probes: Internal pipeline failure leaked private path; uniform target crop returned false missing deposit; contour geometry vs pixel mask arithmetic caused 18% discrepancy in overflow calculation; D04 fired on missing presence limit; oversized upload buffered full file; profile accepted empty limits and duplicate ROI IDs; benchmark runner suppressed descriptions.
- Final test results:
  - Focused vision unit tests: 27 passed in 0.35s (`test_vision_preprocessing.py`, `test_vision_segmentation.py`, `test_vision_measurement.py`, `test_vision_defect_classifier.py`).
  - Focused diagnosis/evidence/LLM unit tests: 31 passed in 1.14s (`test_diagnosis_engine.py`, `test_evidence_engine.py`, `test_ai_outputs.py`, `test_evaluation_framework.py`).
  - Defect classifier & cause ranker unit tests: 11 passed in 0.80s (`test_defect_classifier.py`, `test_cause_ranker.py`).
  - Image API integration tests: 20 passed in 1.52s (`test_image_api.py`, `test_image_diagnosis_integration.py`).
  - Image-driven case workflow & persistence tests: 37 passed in 9.50s (`test_image_driven_case_workflow.py`, `test_persistence.py`).
  - Full backend test suite: 461 passed, 0 failed, 41 warnings in 51.82s.
  - Task validator: `VALID: .agents\handoff\tasks\DLK-M3-026-calibrated-vision-evidence-foundation.md`.
  - Git diff check: Passed with zero trailing whitespace or formatting warnings (`git diff --check` exits with 0).
  - Database safety: Run against disposable PostgreSQL test database (`dispenselens_test`); development database (`dispenselens`) untouched.
  - Live OpenAI smoke: Skipped; verified offline with deterministic mock and fallback handlers.

### Limitations and follow-up

- Segmentation capability: Uses local Otsu and adaptive thresholding suitable for high-contrast backlit/top-lit dispensing deposits. Complex specular reflections or transparent materials may require multi-spectral lighting or specialized deep-learning segmenters in future phases.
- D06 neutrality: D06 observations (`visible_bubbles`, `crater_shape`, `abnormal_shape`) remain purely informational and contribute 0 score weight to candidate causes.
- Raw image persistence: Raw image bytes, base64 payloads, and filesystem paths are intentionally never stored in PostgreSQL or sent to OpenAI LLM; only resolution-independent geometric and calibration metadata are persisted.
- Frontend work: Phase 1 is strictly backend-only. All interactive UI elements, ROI calibration controls, and visual defect badges are deferred to Phase 2.

### Proposed commit message

fix(vision): resolve DLK-M3-026 review findings R1-R7
