---
task_id: DLK-M3-035
title: Preserve every affected region ID in deduplicated image observations
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-034]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-035: Affected-region provenance

## Objective

When several inspected sites show the same defect, keep one diagnostic observation while recording every affected ROI ID. This lets later UI/report work show the actual locations without multiplying diagnostic evidence or changing its score.

## Current evidence

- Local `backend-database` is at `7a55e65f4f3ad3a733289393f6f5a832ba47db52`. DLK-M3-034 is accepted; its review and queue acceptance update are uncommitted planner handoff records to include in this task's commit.
- `backend/app/services/vision/defect_classifier.py` deduplicates observations by `(observation_type, value)` in both PROCESS_LIMITS and REFERENCE_IMAGE. It keeps metadata from the first matching ROI only, losing later affected IDs. The D03 inconsistent-size observation is computed from aggregate CV and currently has no ROI IDs.
- `Observation.metadata` is an existing JSON-compatible dictionary. `backend/tests/integration/test_image_driven_case_workflow.py` verifies that image observation metadata survives durable case creation and retrieval. `backend/app/services/ai/prompt_manager.py` selects a limited set of metadata fields for AI text; it currently does not include a list of ROI IDs.
- `FEATURES_ONLY` produces no observations. Any unassessed current or reference ROI still causes conservative zero-observation gating in calibrated modes. Preserve both.
- The broader roadmap calls for affected-site provenance without duplicate scoring. Frontend display belongs to Member 1; diagnostic weights and interpretation belong to Member 2. This task changes metadata generation only.
- The accepted DLK-M3-034 review records one wording correction: its report claims all self-intersections are rejected, while the code specifically rejects repeated vertices. Correct that sentence as part of this documentation touch.
- Exclude unrelated untracked `.agents.zip` and `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md` from staging.

## Requirements

- Add `metadata.affected_roi_ids` to IMAGE observations generated from calibrated ROI analysis. It must be an ordered, unique list of every ROI that actually triggered that exact `(observation_type, value)` observation, following the supplied ROI order.
- Keep the existing single observation per `(observation_type, value)` behavior. A second matching ROI appends its ID to that observation's metadata; it must not create an additional score-bearing observation or change the first observation's value, source, statement type, or primary `metadata.roi_id`/measurement fields.
- Distinct values retain distinct observations and independent affected-ID lists (for example undersized and oversized). If one ROI meets two independent rule dimensions, its ID appears once in each relevant observation, not twice in the same list.
- In PROCESS_LIMITS, respect existing per-rule limit gates and missing-deposit `continue` behavior. An ROI that did not trigger a rule must never appear in that rule's affected list.
- In REFERENCE_IMAGE, include only current ROI IDs that have a matching reliable reference, a computable comparison, and actually breach the specified rule. Do not include unmatched or near-zero-reference ROIs.
- For D03 inconsistent-size, `affected_roi_ids` identifies the eligible DETECTED, positive-area ROIs that contributed to the aggregate CV calculation. Document that these are comparison participants; it does not assert each participant individually violates a limit. Keep the existing `size_cv` and `max_size_cv` metadata.
- Preserve conservative whole-image gating: any UNASSESSED current or reference site still yields no observations in calibrated modes. FEATURES_ONLY remains neutral. No partial evidence in this task.
- Metadata must remain JSON-compatible and survive durable case create/read using the existing persistence contract. Do not add raw images, masks, or contour points to observation metadata.
- Do not change diagnostic rule weights, duplicate-evidence semantics, engine scoring, case schema, API response envelope, or report/AI prompt projection.

## Interfaces and data contracts

Authorized additive metadata key on existing IMAGE `Observation`: `affected_roi_ids: list[str]`. For per-site rules it lists each violating site; for D03 it lists aggregate comparison participants. Keep `metadata.roi_id` and first-site metrics for backward compatibility when already present. No new endpoint or database column. Existing observations without this metadata remain valid.

This task provides provenance to the existing image API and case metadata path. It does not claim that the current frontend, AI summary, or reports display the full list; their consumers need later scoped work and owner review.

## Allowed paths

- `backend/app/services/vision/defect_classifier.py`
- `backend/tests/unit/test_vision_defect_classifier.py`
- `backend/tests/integration/test_image_api.py`
- `backend/tests/integration/test_image_diagnosis_integration.py`
- `backend/tests/integration/test_image_driven_case_workflow.py`
- `backend/tests/fixtures/synthetic_images.py` only if a real-image multi-site fixture is needed
- `docs/api/api-spec.md`
- `docs/architecture/region-inspection-improvement-plan.md` for one brief progress note
- `.agents/handoff/tasks/DLK-M3-034-bounded-deposit-outline.md` for the precise self-intersection wording correction only
- `.agents/handoff/tasks/DLK-M3-035-affected-region-provenance.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-034-review.md` (include planner-authored accepted review unchanged)

## Prohibited scope

Frontend edits, changing diagnostic weights or knowledge rules, changing metadata projection into AI prompts or reports, partial evidence, segmentation/geometry algorithm changes, response profile changes, database migrations, new dependencies, full image storage, template/alignment work, remote Git operations, and changes to main.

## Implementation guidance

1. Confirm branch, prerequisite acceptance, parent commit, and working tree. Read repository instructions and scoped tests. Preserve unrelated files and the accepted review record.
2. Add failing focused tests that demonstrate two sites with the same defect currently retain only the first ID, then implement the metadata aggregation. Use one internal aggregation mechanism for all ROI-level rule paths; avoid duplicating update logic across seven conditions.
3. Add tests for separate values, one ROI triggering multiple dimensions, rule/limit gating, D03 participant IDs, reference matching, and unassessed gating. At least one API test should use a synthetic two-site image rather than only manually constructed measurements.
4. Verify one versus two same-defect sites still produce one canonical observation and identical diagnosis contribution for that observation; do not alter Member 2 scoring code. Extend the existing durable case workflow to assert `affected_roi_ids` survives create/read. Use only the safe disposable test database.
5. Update API documentation and a short roadmap progress note. Correct the DLK-M3-034 report sentence so it claims repeated-vertex rejection, not blanket self-intersection detection.
6. Inspect final diff, complete this report, set queue status to implemented, then create one local commit after required checks pass.

## Acceptance criteria

- [x] PROCESS_LIMITS emits one observation for two or more ROIs with the same rule/value, with every violating ID in input order and no duplicates.
- [x] Different values and rule dimensions have independent exact affected-ID lists; nonviolating sites are absent.
- [x] REFERENCE_IMAGE preserves exact affected IDs only for matched, evaluated, violating sites.
- [x] D03 metadata lists the eligible aggregate CV participants and states their role accurately in documentation.
- [x] FEATURES_ONLY and UNASSESSED gates still emit zero observations; observation count and scoring contribution for duplicate sites remain unchanged.
- [x] A real synthetic multi-site API path and the durable case create/read path preserve `affected_roi_ids` without altering existing metadata.
- [x] No new DB/API envelope fields, diagnostic weights, frontend changes, or unreviewed scope. Prior self-intersection wording is corrected narrowly.
- [x] Required checks pass and only task-related files are committed locally.

## Verification

Run from repository root in PowerShell. Before database-backed tests, use the existing safe disposable `TEST_DATABASE_URL` bootstrap; never bypass the safeguard or touch development data.

1. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_defect_classifier.py backend/tests/integration/test_image_api.py backend/tests/integration/test_image_diagnosis_integration.py backend/tests/integration/test_image_driven_case_workflow.py -q --basetemp=backend/.task035-focused -p no:cacheprovider`
2. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task035-full -p no:cacheprovider`
3. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-035-affected-region-provenance.md`
4. `git diff --check`

If required infrastructure is unavailable, record the blocker and do not report the task as implemented. Frontend checks are not required because frontend code is excluded.

## Planner decision boundaries

The additive `affected_roi_ids` metadata key and deduplicated ROI aggregation are authorized in Member 3 scope. Return to the planner before changing observation type/value, diagnosis engine scoring, partial-evidence semantics, public request/response shapes, persistence schema, AI/report projection, or frontend ownership. Later display and interpretation of affected sites require the relevant teammate's review.

## Git instructions

Commit this packet, its implementation report, queue, pending accepted DLK-M3-034 review, narrow documentation correction, and scoped code/tests in one atomic local commit after checks pass. Do not stage unrelated files. Do not push, merge, rebase, create a PR, or change main.

Proposed commit message: `feat(vision): preserve affected ROI IDs in image observations`

## Implementation report

### Summary

Implemented `metadata.affected_roi_ids` across all defect classification rules in `backend/app/services/vision/defect_classifier.py` (`PROCESS_LIMITS` and `REFERENCE_IMAGE`). The classifier preserves deduplication by `(observation_type, value)`, ensuring single diagnostic observation emission without inflating diagnosis engine scores or evidence weights. Primary metadata (`roi_id`, measurements) is preserved from the first matching ROI, while `affected_roi_ids` records an ordered, deduplicated list of all breaching ROI IDs in input order. For `D03_INCONSISTENT_SIZE`, `affected_roi_ids` contains `d03_participant_ids` (all `DETECTED` ROIs with `deposit_area_px > 0` contributing to the coefficient of variation calculation). The `affected_roi_ids` list safely survives durable case creation and round-trip retrieval in PostgreSQL. Unassessed region gating and `FEATURES_ONLY` neutral behavior remain intact.

### Files changed

- `backend/app/services/vision/defect_classifier.py`: Centralized observation creation into `_record_observation` helper tracking ordered unique `affected_roi_ids` across all defect rules in both `PROCESS_LIMITS` and `REFERENCE_IMAGE` modes, and populated `affected_roi_ids` with `d03_participant_ids` for D03.
- `backend/tests/unit/test_vision_defect_classifier.py`: Added 7 focused unit tests verifying multi-ROI aggregation, independent defect value tracking, multi-dimensional rule triggering, non-violating ROI exclusion, missing-deposit skipping, D03 participant recording, and reference mode matching/shape deduplication.
- `backend/tests/integration/test_image_api.py`: Added 2 end-to-end integration tests using synthetic multi-ROI images to verify `affected_roi_ids` propagation in `PROCESS_LIMITS` and `REFERENCE_IMAGE` analysis modes.
- `backend/tests/integration/test_image_diagnosis_integration.py`: Added integration test asserting that multiple sites with identical defect values yield identical diagnosis scores to single-site breaches (no score inflation).
- `backend/tests/integration/test_image_driven_case_workflow.py`: Updated single-ROI end-to-end test and added multi-site durable case test verifying `affected_roi_ids` persists and round-trips correctly across case revisions in PostgreSQL.
- `docs/api/api-spec.md`: Documented `affected_roi_ids` in `metadata` schema, updated example JSON payload, outlined provenance contract, and clarified that affected ROI lists are exact per observation and may overlap across different rules (resolving review R1).
- `docs/architecture/region-inspection-improvement-plan.md`: Updated Phase 1 increment status for DLK-M3-035.
- `.agents/handoff/tasks/DLK-M3-034-bounded-deposit-outline.md`: Corrected wording regarding nonconsecutive repeated vertex rejection.
- `.agents/handoff/tasks/DLK-M3-035-affected-region-provenance.md`: Updated status to implemented, completed implementation report, marked supported acceptance checkboxes, and corrected reference-mode skip vs UNASSESSED gating description (resolving review R2).
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-035 status to implemented with R1/R2 resolution details.
- `.agents/handoff/reviews/DLK-M3-035-review.md`: Review record addressing R1 and R2.

### Decisions made

- `_record_observation` helper: Factored out common observation registration logic into a private helper function. When a `(observation_type, value)` key already exists in `obs_by_key`, the helper appends new unique `roi_id` entries to `metadata["affected_roi_ids"]` in input order without altering first-site primary metrics.
- D03 participant provenance: The D03 inconsistent deposit size defect is computed over aggregate area variation across detected deposits. Populated `metadata["affected_roi_ids"]` with `d03_participant_ids` (all `DETECTED` ROIs with `deposit_area_px > 0`) to accurately reflect all deposits evaluated in the comparison.
- Reference shape deduplication: In `REFERENCE_IMAGE` mode, both circularity and solidity breaches emit `("deposit_shape", "abnormal")`. Checking `roi_id not in affected` ensures that an ROI triggering both shape rules is recorded only once in `affected_roi_ids`.
- Schema & diagnosis preservation: Preserved `Observation` schema and PostgreSQL `case_observations` JSONB storage without requiring database migrations. Kept Member 2 causal scoring and rule weights intact.

### Verification results

1. Focused test suite:
   `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_defect_classifier.py backend/tests/integration/test_image_api.py backend/tests/integration/test_image_diagnosis_integration.py backend/tests/integration/test_image_driven_case_workflow.py -q --basetemp=backend/.task035-focused -p no:cacheprovider`
   Result: `65 passed, 20 warnings in 2.59s`
2. Full backend test suite:
   `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task035-full -p no:cacheprovider`
   Result: `555 passed, 42 warnings in 58.39s`
3. Task validation script:
   `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-035-affected-region-provenance.md`
   Result: Validated (0 errors).
4. Whitespace check:
   `git diff --check`
   Result: Clean (0 whitespace errors).

### Limitations and follow-up

- Frontend display of `affected_roi_ids` (e.g. multi-site highlight badges on image viewer and case report) is owned by Member 1 and was not modified in this task.
- AI prompt manager currently filters metadata keys when constructing LLM context. Adding `affected_roi_ids` to prompt narratives can be addressed in a future task if desired.
- In `REFERENCE_IMAGE` mode, current regions missing a matching reference region are safely skipped with an explanatory warning while matched regions are evaluated normally. In contrast, any region with an `UNASSESSED` inspection status in either current or reference images retains the whole-image conservative gate (suppressing all observations).

### Proposed commit message

`docs(vision): clarify affected ROI list isolation and reference mode skip behavior`
