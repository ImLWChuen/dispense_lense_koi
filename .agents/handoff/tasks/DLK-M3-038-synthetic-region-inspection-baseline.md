---
task_id: DLK-M3-038
title: Establish a repeatable synthetic region-inspection baseline
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-037]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-038: Synthetic region-inspection baseline

## Objective

Create a repeatable, offline evaluation of the current region inspection pipeline on a small, labeled **synthetic** fixture set. Report whether expected sites are classified as `DETECTED`, `MISSING`, or `UNASSESSED`, whether bounded outlines are available for detected deposits, and how closely those outlines match simple known drawn masks. This establishes an honest baseline before tuning segmentation or claiming industrial accuracy.

## Current evidence

- DLK-M3-037 is accepted at `a124dbcd5a6cd58c54f0435c548bdf95348e9442`; its accepted review and queue update are uncommitted planner handoff records to include in this task's local commit.
- `backend/app/api/images.py` implements `_sync_analyze_image`, the same image-processing path used by `POST /api/v1/images/analyze`. It returns per-ROI `inspection_status`, optional `deposit_outline_normalized`, warnings, current/reference coverage, and canonical observations.
- `backend/tests/fixtures/synthetic_images.py` contains deterministic dot, empty-with-fiducials, shape, and multi-ROI generators, but `create_noisy_image` uses unseeded randomness. Existing tests cover individual cases, not a fixed fixture manifest or summary metrics. `backend/app/evaluation/benchmark.py` evaluates the **diagnostic engine**, not vision inspection.
- `docs/architecture/region-inspection-improvement-plan.md` Phase 0 calls for fixture scope and known boundaries; Phase 5 calls for measured baseline, abstention, and later real-image evaluation. The roadmap still lacks representative production images and independent labels. This task must not manufacture such evidence.
- The existing repository-specific `AGENTS.md` governs work. Preserve unrelated untracked `.agents.zip` and `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md`; do not stage them.

## Requirements

- Add a test-support-only, deterministic fixture manifest with stable case IDs, capture description, generated image bytes, configured expected ROI IDs/geometry, independently specified expected inspection status per site, and simple ground-truth binary deposit masks **only** for cases where geometry is known by construction. Keep labels separate from actual pipeline outputs.
- Include at minimum: one clean detected dot, one confirmed missing expected site with the existing fiducial-style context, one uniform/unassessed site, a mixed detected-plus-unassessed image, and a two-site detected image. A clipped or ambiguous example is welcome only if its expected label is justified from construction and deterministic. Do not use unseeded `create_noisy_image` in the baseline.
- Run each case through `_sync_analyze_image` using a valid explicit profile; do not access production data, use a database, call an LLM/network service, or write source images to persistent storage. Derive predicted site statuses and outlines from the **actual** response, not from the fixture label.
- Compute transparent metrics with explicit numerator/denominator: per-status confusion counts; status accuracy across labeled expected sites; unassessed/abstention count and rate; false-missing count for sites labeled unassessed; outline availability among detected sites with known masks; and mean polygon-mask IoU only where both an expected mask and a valid returned outline exist. Rasterize the response's full-image normalized polygon at fixture dimensions; do not compare masks in mismatched coordinate systems. If an outline is absent, report that omission separately rather than assigning an invented IoU.
- Print a bounded, machine-readable JSON summary with fixture IDs, expected/predicted statuses, per-case warnings (truncated/bounded if needed), metrics and denominators, and timing as descriptive measurements only. No pass/fail threshold for model performance, no claim about production accuracy, and no filesystem write by default.
- Add an evaluation document recording the fixed fixture manifest, supported capture assumptions, the exact command, baseline output produced during implementation, any mismatches or exclusions, machine/runtime context for timing, and the limits of synthetic evidence. If a fixture fails an expected status, **report it**; do not alter labels or tune the CV pipeline inside this task to make the result look better.
- Preserve all production schemas, API behavior, diagnosis scoring, frontend behavior, and current fixture/test expectations. This task evaluates; it does not change the segmentation classifier or thresholds.

## Interfaces and data contracts

- No product API or database contract changes. The new runner lives under `backend/tests/` as offline evaluation support. It may expose a small testable pure function for computing metrics from manifest labels and response projections.
- CLI entry point: from `backend/`, `.\.venv\Scripts\python.exe -m tests.vision_inspection_baseline`. It prints UTF-8 JSON to stdout; errors go to stderr with nonzero exit. Do not require a running backend, PostgreSQL, or external services for this CLI.
- Keep per-case output bounded: include only site IDs, expected/predicted statuses, concise warnings, outline presence/IoU, and elapsed time; do not emit image bytes, raw masks, image paths, or huge polygons.
- `COMPLETE` inspection coverage is not defect-free acceptance. Existing top-level `UNRELIABLE` status and zero-observation behavior on mixed/unassessed images remain unchanged. The benchmark must make this distinction visible in its documented interpretation.

## Allowed paths

- `backend/tests/vision_inspection_baseline.py` (new)
- `backend/tests/unit/test_vision_inspection_baseline.py` (new)
- `backend/tests/fixtures/synthetic_images.py` only for deterministic fixture helpers or masks needed by the runner
- `docs/evaluation/region-inspection-synthetic-baseline.md` (new)
- `docs/architecture/region-inspection-improvement-plan.md` for a brief Phase 0/5 progress note
- `.agents/handoff/tasks/DLK-M3-038-synthetic-region-inspection-baseline.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-037-review.md` (include planner-authored accepted review unchanged)

## Prohibited scope

Production CV/API/schema changes; modifying diagnostic rules, model weights, thresholds, or existing expected test outcomes; frontend or database changes; adding dependencies; recording user/production images; representing synthetic scores as industrial accuracy; automatic alignment or template storage; remote Git operations; changes to main.

## Implementation guidance

1. Confirm branch and accepted prerequisite, read scoped files and repository instructions, and preserve unrelated changes. Review existing synthetic test images and decide on the smallest deterministic manifest; record it before interpreting results.
2. Implement pure metric computation and focused tests using hand-constructed label/prediction examples, including a deliberately wrong prediction, false missing, absent outline, empty IoU denominator, and a known polygon/mask overlap. This verifies the evaluator independently of the CV pipeline.
3. Implement the runner using `_sync_analyze_image`, the manifest, and in-memory images/masks. Use a stable ordering of cases and site IDs. Bound warnings and output size. Make elapsed-time measurements descriptive, not assertions.
4. Run the CLI, capture its actual JSON summary, and document the observed baseline and mismatches without changing labels or product code. Add a smoke test of the real runner that verifies the schema and non-empty case coverage without asserting a fabricated performance target.
5. Run required checks, inspect the diff for images/secrets/generated output, complete this report, set queue status to implemented, and create one scoped local commit.

## Acceptance criteria

- [x] The fixed manifest contains the required deterministic synthetic scenarios with stable expected site IDs/status labels; known shape masks are independent of pipeline outputs.
- [x] The offline command runs without server, database, network, or persisted images and outputs bounded, parseable JSON with per-case outcomes and explicit metric denominators.
- [x] Unit tests demonstrate correct confusion accounting, abstention and false-missing rates, outline availability, IoU alignment/math, omission behavior, and no division-by-zero fabrication.
- [x] The real-run smoke test exercises the image-processing path and preserves its statuses, warnings, outlines, and conservative mixed-image gating without altering product code.
- [x] The documented baseline includes actual observed results, mismatches/exclusions, capture assumptions, exact run command, and a clear statement that synthetic results do not establish real manufacturing accuracy.
- [x] Only scoped test-support/docs/handoff files are committed locally after focused and full backend checks; no remote Git operation occurs.

## Verification

From repository root in PowerShell, use the established backend virtual environment. The runner itself must not need database configuration; the full backend suite uses the existing safe disposable `TEST_DATABASE_URL` setup and must never bypass destination safeguards.

1. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_inspection_baseline.py -q --basetemp=backend/.task038-focused -p no:cacheprovider`
2. From `backend/`: `.\.venv\Scripts\python.exe -m tests.vision_inspection_baseline` (inspect actual JSON output; record values in the evaluation document).
3. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task038-full -p no:cacheprovider`
4. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-038-synthetic-region-inspection-baseline.md`
5. `git diff --check` and inspect staged/unstaged files before committing.

If a required check is unavailable, record the blocker and report `blocked`. Do not substitute a claimed baseline for an unrun command.

## Planner decision boundaries

The test-support-only synthetic baseline and evaluation documentation above are authorized. Return to the planner before changing production CV behavior, target thresholds, public API, data retention, frontend ownership, diagnostic scoring, material dependencies, or adding real/third-party images. Real-image collection and quantitative acceptance targets require separate team decisions and credible labels.

## Git instructions

Commit this task packet, completed implementation report, queue, pending accepted DLK-M3-037 review, scoped tests/fixture support, and evaluation document in one atomic local commit after checks pass. Do not stage unrelated files. Do not push, merge, rebase, create a PR, or change main.

Proposed commit message: `test(vision): establish synthetic region inspection baseline`

## Implementation report

### Summary

Established an offline, deterministic evaluation harness and baseline report for the DispenseLens region-inspection computer vision pipeline (`_sync_analyze_image`) using a fixed 6-case synthetic manifest (`synthetic_region_inspection_baseline_v1`) covering 9 expected dispensing sites. Built the offline CLI runner (`backend/tests/vision_inspection_baseline.py`) which computes status confusion matrices, accuracy, abstention rate, false-missing safety rate, outline availability, and mean polygon-mask IoU against construction-grounded circular masks without server, database, network, or image persistence dependencies. Added unit tests verifying evaluator calculations independently of the CV pipeline, and created `docs/evaluation/region-inspection-synthetic-baseline.md` documenting the baseline results, capture assumptions, reproduction commands, and the strict limits of synthetic evidence.

### Files changed

- `backend/tests/vision_inspection_baseline.py` (new): Implemented the offline baseline runner, deterministic fixture manifest, polygon rasterization, IoU calculation, confusion matrix, metric aggregations with explicit numerators/denominators, and JSON CLI entry point.
- `backend/tests/unit/test_vision_inspection_baseline.py` (new): Added unit tests for metric accounting, confusion matrix building, false-missing/abstention rates, outline availability/omissions, zero-denominator safety, polygon rasterization, and runner smoke test verifying schema and conservative gating.
- `backend/tests/fixtures/synthetic_images.py`: Added deterministic fixture generators `create_mixed_detected_and_unassessed_image` and `create_mixed_detected_and_missing_image` for multi-site scenario evaluation.
- `docs/evaluation/region-inspection-synthetic-baseline.md` (new): Created comprehensive evaluation report recording manifest details, capture assumptions, reproduction commands, exact observed JSON output, metric summaries, and synthetic evidence boundaries.
- `docs/architecture/region-inspection-improvement-plan.md`: Added progress notes for increment DLK-M3-038 under Phase 0 and Phase 5.
- `.agents/handoff/tasks/DLK-M3-038-synthetic-region-inspection-baseline.md`: Recorded implementation status, completed acceptance criteria, and filled implementation report.
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-038 status to `implemented`.

### Decisions made

- Kept ground-truth masks strictly limited to cases where geometry is known by construction (circular dot deposits); omitted masks for missing and uniform unassessed sites so IoU is evaluated only where valid outlines are expected.
- Explicitly documented that synthetic evaluation results demonstrate software behavior and contract consistency, and do not represent industrial production accuracy or defect recall.
- Preserved existing production CV code, classifier thresholds, and API behavior unchanged; this task is strictly evaluation and test support.

### Verification results

- Focused pytest suite: `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_inspection_baseline.py -q --basetemp=backend/.task038-focused -p no:cacheprovider` -> `6 passed in 0.56s`
- Baseline CLI runner: `.\.venv\Scripts\python.exe -m tests.vision_inspection_baseline` (from `backend/`) -> Exit 0, 9/9 sites evaluated in 0.0168s, 100% status accuracy, 0.0% false-missing, 100% outline availability, 0.9970 mean IoU.
- Full backend pytest suite: `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task038-full -p no:cacheprovider` -> `577 passed, 42 warnings in 62.39s`
- Task packet validation: `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-038-synthetic-region-inspection-baseline.md` -> `VALID`
- Whitespace validation: `git diff --check` -> Clean (code 0)

### Limitations and follow-up

- The baseline uses synthetic images only; evaluation on physically captured production PCB images with technician ground-truth labels remains a prerequisite before claiming industrial accuracy (Phase 5).
- No production CV tuning or threshold changes were made in this task.
- Automated image alignment and persistent layout templates remain deferred to Phase 3.

### Proposed commit message

`test(vision): establish synthetic region inspection baseline`
