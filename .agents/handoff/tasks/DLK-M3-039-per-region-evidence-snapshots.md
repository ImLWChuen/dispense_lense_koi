---
task_id: DLK-M3-039
title: Preserve per-region measurements and limits in image evidence
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-038]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-039: Per-region evidence snapshots

## Objective

When one image observation represents several affected regions, preserve each region's own measurements and the supplied limits through durable case creation and retrieval. This makes the recorded evidence usable for later region-specific explanations without treating the first region's measurements as measurements of every affected site. This is a Member 3 provenance increment toward roadmap Phase 4; it does not complete the frontend workbench or change diagnostic meaning.

## Current evidence

- DLK-M3-038 is accepted at `899d36d64e7d04f0734423eb190b872fb2ac4d77`; its accepted review and queue edits are pending planner artifacts to include in this task's local commit.
- `backend/app/services/vision/defect_classifier.py::_record_observation` keeps ordered unique `affected_roi_ids` but preserves only the first site's scalar metadata. Different sites can have different measurements despite sharing the same observation type/value.
- Reference classification computes coverage, circularity, and solidity comparisons using matching reference regions. Some of those inputs and supplied limits are not retained in existing observation metadata.
- D03 inconsistent size is an aggregate comparison: affected IDs represent eligible comparison participants, not individually failed regions.
- `backend/tests/integration/test_image_driven_case_workflow.py` already verifies image metadata persists through case creation, retrieval, and a later revision. Observation metadata is an existing JSON field; no database migration is required for additive contents.
- The current conservative gates suppress all calibrated observations for unassessed images. Preserve this behavior. Frontend ownership, partial evidence, reusable layouts, alignment, and real-image evaluation remain separate decisions/tasks.

## Requirements

- Enrich only already-emitted calibrated IMAGE observations with additive metadata. Preserve existing metadata keys/values, observation ordering, affected ID ordering, source, statement type, type/value pairs, and deduplication behavior.
- Add `region_evidence`: one entry per ID in `affected_roi_ids`, in exactly that order. No duplicate entries when multiple conditions produce the same observation for one site. Include only sites already associated with that observation, not every configured site.
- Each entry contains `roi_id`, `current_measurements`, and `reference_measurements`. Current measurements come from that exact site's `RoiMeasurement`; reference measurements come only from its matching reference site in reference mode, otherwise null.
- Use the fixed scalar measurement allowlist below. Do not serialize entire models, geometry, masks, image contents, paths, bubble details, or arbitrary metadata. Snapshot values must be detached from input objects so later mutation cannot rewrite recorded evidence.
- Add `applied_limits`: the active validated process or reference limits serialized with JSON-compatible values and null fields omitted. Reference snapshots include the resolved effective bounds when `tolerance_ratio` supplies them. These are configuration snapshots, not a claim that every supplied limit was violated or evaluated for that observation.
- Add `region_evidence_scope`: `individual_regions` for ordinary site findings; `comparison_group` for the existing D03 `deposit_size=inconsistent` observation. For D03, capture precisely its current eligible positive-area DETECTED participants and retain existing `size_cv`/`max_size_cv` metadata. Do not assign individual outlier or pass/fail labels.
- Preserve all existing rule thresholds, comparisons, missing-deposit short-circuit behavior, quality gates, unmatched-reference handling, near-zero denominator handling, D06 scoring neutrality, and diagnostic scores. Features-only and unreliable paths remain observation-free.
- Verify the additive snapshots survive the existing durable create/read and later revision paths. Existing observations without these fields remain valid; never backfill fabricated provenance.

## Interfaces and data contracts

Only additive contents of `Observation.metadata` are authorized; existing endpoint schemas, database contracts, and scoring interfaces remain unchanged.

```json
{
  "region_evidence_scope": "individual_regions",
  "applied_limits": {"min_coverage_ratio": 0.5},
  "region_evidence": [
    {
      "roi_id": "site_a",
      "current_measurements": {"coverage_ratio": 0.3},
      "reference_measurements": null
    }
  ]
}
```

The example abbreviates measurement contents. Required allowlist for both current and reference snapshots: `inspection_status`, `deposit_area_px`, `target_area_px`, `coverage_ratio`, `overflow_ratio`, `equivalent_diameter_px`, `calibrated_diameter_mm`, `circularity`, `solidity`, `convexity`, `aspect_ratio`, `hole_void_ratio`, `bubble_count`, `has_bubbles`, `segmentation_quality`. Preserve null physical diameter when uncalibrated; serialize enums as their string values. No computed root-cause conclusions, derived pass/fail labels, or duplicate score contributions.

In reference mode, the saved current/reference scalars plus effective limits must permit a consumer to reconstruct the existing comparisons; do not add a second classification algorithm. Legacy first-site scalar metadata remains for compatibility and must be documented as describing only that site. Missing new fields mean provenance was not recorded, not zero measurements or successful inspection.

## Allowed paths

- `backend/app/services/vision/defect_classifier.py`
- `backend/tests/unit/test_vision_defect_classifier.py`
- `backend/tests/integration/test_image_api.py`
- `backend/tests/integration/test_image_diagnosis_integration.py`
- `backend/tests/integration/test_image_driven_case_workflow.py`
- `docs/api/api-spec.md`
- `docs/architecture/region-inspection-improvement-plan.md` (brief progress note only)
- `.agents/handoff/tasks/DLK-M3-039-per-region-evidence-snapshots.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-038-review.md` (include planner-authored accepted review unchanged)

## Prohibited scope

Frontend changes; segmentation/measurement tuning; new diagnostic rules or score changes; partial score-bearing analysis; report/PDF rendering changes; database migrations or new retention; reusable profiles/alignment; dependencies; new API routes; remote Git operations or changes to main. Preserve unrelated `.agents.zip` and `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md`.

## Implementation guidance

1. Read repository instructions, PROJECT.md, QUEUE.md, prerequisite review, classifier, schemas, and existing provenance tests. Confirm branch and pending files.
2. Add focused regression cases for distinct measurements on sites sharing an observation, reference comparison snapshots, and D03 participants. Confirm new assertions expose the current missing provenance before implementation.
3. Add a small private snapshot/projection helper and enrich existing emitted observations without moving or rewriting classification conditions. A final enrichment pass over the already-established observation IDs is acceptable if it preserves all gates and input ordering. Use explicit field allowlists and detached dictionaries.
4. Cover multiple predicates on one region without duplicate region entries; per-observation isolation; resolved reference bounds; JSON serialization; input immutability; and old metadata compatibility. Ensure group evidence is identified explicitly.
5. Extend the actual image API and durable workflow tests to verify different per-site values are preserved, including after a later revision. Compare engine results with/without the new metadata to show ranking/score/evidence-count parity, using existing integration infrastructure.
6. Document the metadata contract and boundaries. Run checks on the final code, complete the report, update queue to implemented, and commit scoped files locally.

## Acceptance criteria

- [x] Two sites with different measurements contributing the same finding produce one observation with two correctly matched, ordered snapshots and unchanged legacy metadata.
- [x] Separate observations contain only their own affected sites; multiple conditions on one site never duplicate its snapshot.
- [x] Reference evidence contains the matching current/reference scalars and resolved effective limits; process evidence contains no invented reference measurements.
- [x] D03 snapshots describe eligible comparison participants with `comparison_group`, retain aggregate metrics, and do not imply individual failure.
- [x] Snapshots are JSON-compatible, detached, and limited to the specified fields. No raw images, contours, masks, or unbounded per-site diagnostic payloads are added.
- [x] Real API response and durable create/read/later-revision tests preserve all new metadata; legacy observations continue to deserialize without fabricated values.
- [x] Observation membership, ordering, score semantics, reliability gates, features-only neutrality, and D06 neutrality are unchanged, with meaningful regression evidence.
- [x] Focused/full checks pass against final code, documentation reflects actual behavior, and only scoped files are committed locally.

## Verification

From repository root in PowerShell. Use the existing safe disposable `TEST_DATABASE_URL` configuration for database-backed tests; do not print credentials, target development data, or bypass destination safeguards. The environment and commands already exist.

1. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_defect_classifier.py backend/tests/integration/test_image_api.py backend/tests/integration/test_image_diagnosis_integration.py backend/tests/integration/test_image_driven_case_workflow.py -q --basetemp=backend/.task039-focused -p no:cacheprovider`
2. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task039-full -p no:cacheprovider`
3. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-039-per-region-evidence-snapshots.md`
4. `git diff --check` and inspect staged diff before committing.

Record actual results after the final code changes. If a required check cannot run, record the exact blocker and mark blocked rather than carrying forward an older result. No frontend checks are required because frontend files are out of scope.

## Planner decision boundaries

The additive metadata contract above is authorized. Return to the planner before changing classification or score meaning, eligibility of any site, API schemas, persistence behavior, dependencies, ownership boundaries, or scope. If existing storage fails to preserve the new JSON contents, report the evidence before modifying repository/storage code outside the allowlist. Real-image accuracy targets and image retention remain undecided.

## Git instructions

Create one atomic local commit on `backend-database` after checks pass. Include the completed task packet, queue, and pending accepted DLK-M3-038 review unchanged. Preserve unrelated files. Do not push, merge, rebase, create a PR, or modify main.

Proposed commit message: `feat(vision): preserve per-region evidence snapshots`

## Implementation report

### Summary

Implemented additive per-region evidence snapshots and applied limits in image observations for calibrated vision analysis (`PROCESS_LIMITS` and `REFERENCE_IMAGE` modes). Emitted observations now retain:
- `region_evidence_scope`: `"individual_regions"` for ordinary defect findings; `"comparison_group"` for D03 `deposit_size=inconsistent`.
- `applied_limits`: caller-supplied process or reference limits with null values omitted, including resolved effective comparison bounds from `tolerance_ratio`.
- `region_evidence`: ordered list of detached measurement snapshots strictly matching `affected_roi_ids`. Each snapshot contains exactly the 15-field scalar allowlist (`inspection_status`, `deposit_area_px`, `target_area_px`, `coverage_ratio`, `overflow_ratio`, `equivalent_diameter_px`, `calibrated_diameter_mm`, `circularity`, `solidity`, `convexity`, `aspect_ratio`, `hole_void_ratio`, `bubble_count`, `has_bubbles`, `segmentation_quality`), with matching reference snapshots in reference mode or `null` in process mode.

Legacy first-site metadata keys, observation deduplication, diagnostic scoring contributions, and conservative reliability gates remain completely intact. Verified lossless persistence through durable case creation, retrieval, and Revision 2 in PostgreSQL.

### Files changed

- `backend/app/services/vision/defect_classifier.py`: Added `_snapshot_roi_measurements` and `_enrich_observations_with_evidence_snapshots`; invoked prior to returning observations in `PROCESS_LIMITS` and `REFERENCE_IMAGE` branches.
- `backend/tests/unit/test_vision_defect_classifier.py`: Added 6 unit tests covering distinct multi-site measurements, reference mode matching/reconstruction, D03 comparison group scope/participants, multiple conditions deduplication, separate observation isolation, and detached scalar immutability.
- `backend/tests/integration/test_image_api.py`: Added API integration test verifying that `/api/v1/images/analyze` responses carry `region_evidence_scope`, `applied_limits`, and `region_evidence`.
- `backend/tests/integration/test_image_diagnosis_integration.py`: Added diagnostic parity test verifying identical scores, rankings, and evidence counts between legacy and enriched observations.
- `backend/tests/integration/test_image_driven_case_workflow.py`: Added durable lifecycle integration test verifying snapshots persist losslessly through PostgreSQL case creation, retrieval, and revision 2.
- `docs/api/api-spec.md`: Updated response example and added detailed specification subsection for per-region evidence snapshots, scopes, limits, and backward compatibility.
- `docs/architecture/region-inspection-improvement-plan.md`: Added Phase 4 progress note documenting DLK-M3-039 implementation.
- `.agents/handoff/tasks/DLK-M3-039-per-region-evidence-snapshots.md`: Updated task status to implemented, checked all acceptance criteria, and completed implementation report.
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-039 status to implemented.

### Decisions made

- **Single deterministic enrichment pass:** Placed `_enrich_observations_with_evidence_snapshots` right before the return statement in calibrated classification branches. This ensures all early returns, safety gates, defect detection rules, thresholds, short-circuits, and observation deduplication logic remain untouched.
- **Detached scalar dictionary projection:** Restricted snapshot extraction strictly to the 15 allowed scalar fields, explicitly casting to native Python primitives (`float`, `int`, `bool`, `str`, `None`). This prevents any reference mutation or exposure of raw image data, geometry, masks, or contours.
- **D03 comparison group semantics:** Set `region_evidence_scope = "comparison_group"` for D03 `deposit_size=inconsistent`, capturing snapshots only for eligible detected positive-area participants while retaining `size_cv` and `max_size_cv` and omitting any pass/fail or outlier labels.
- **Reference limit reconstruction:** In reference mode, `applied_limits` includes resolved `min_reference_ratio` and `max_reference_ratio` from `tolerance_ratio`, enabling consumers to reconstruct coverage/shape comparisons without a secondary classifier.

### Verification results

- **Focused test suite:** `82 passed, 20 warnings in 5.12s`
  `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_defect_classifier.py backend/tests/integration/test_image_api.py backend/tests/integration/test_image_diagnosis_integration.py backend/tests/integration/test_image_driven_case_workflow.py -q --basetemp=backend/.task039-focused -p no:cacheprovider`
- **Full backend test suite:** `587 passed, 42 warnings in 69.47s`
  `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task039-full -p no:cacheprovider`
- **Task validation:** `VALID: .agents\handoff\tasks\DLK-M3-039-per-region-evidence-snapshots.md`
  `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-039-per-region-evidence-snapshots.md`
- **Whitespace check:** `git diff --check` passed cleanly with 0 errors.

### Limitations and follow-up

- Frontend visual workbench rendering of per-region evidence remains scheduled for subsequent phases (Member 1 frontend ownership).
- Unassessed and unreliable images continue to produce zero score-bearing observations under existing conservative safety gates; partial score-bearing analysis remains deferred.
- No database migration was introduced; PostgreSQL JSONB observation storage preserves the additive metadata without schema alterations.

### Proposed commit message

`feat(vision): preserve per-region evidence snapshots`

Record the resulting commit hash in the completion message; a commit cannot contain its own final hash.
