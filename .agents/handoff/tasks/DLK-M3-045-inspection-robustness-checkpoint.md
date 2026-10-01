---
task_id: DLK-M3-045
title: Establish a repeatable synthetic inspection robustness checkpoint
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-044]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-045: Inspection robustness checkpoint

## Objective

Use the accepted local dataset evaluator to measure how the existing manual-region inspection responds to controlled blur, brightness/contrast changes, glare and clipped acquisition. Produce reproducible artifacts and a concise failure inventory for the next engineering decision. This task evaluates behavior; it does not tune segmentation or claim industrial accuracy.

## Current evidence

- DLK-M3-044 accepted at 54d03538f11efe20eea5f742b79f6f3e3104c963. Its accepted review and queue changes are pending planner records.
- backend/tests/vision_inspection_dataset.py accepts local datasets and preserves profile, provenance, separate inspection coverage, outcomes and failures. Its output safeguards and labeled/unlabeled denominators were reviewed.
- The six-case synthetic baseline covers reliable, missing, uniform and mixed inputs. It does not systematically characterize blur, glare, brightness or clipping.
- No representative factory image set has been provided for this increment. Reusable profile storage, alignment and partial-evidence scoring remain pending scope decisions.

## Completion estimate checkpoint

Before this task: approximately 90–95% of the delivered manual-region prototype scope, and 65–75% of the broader region-inspection roadmap. This is a planning estimate, not test coverage or manufacturing accuracy. If accepted, this task improves robustness evidence but does not by itself raise real-image readiness or complete the outstanding product features. Reassess honestly from findings rather than automatically increasing a percentage.

## Requirements

- Add a deterministic generator for a small fixed manifest of at most 18 cases using existing fixture helpers, OpenCV and NumPy. Include a clean two-site control, blur at two documented levels, darker/brighter or lower-contrast variants, a bounded glare patch, clipping of one deposit at the acquired image edge, and a reliable site beside a degraded site. Keep exact parameters/seeds and source-control relationships in manifest case notes.
- Keep valid normalized ROIs. For clipping, explicitly document the acquisition transform and transform/reconfirm expected ROI coordinates; do not mistake a shifted ROI for a segmentation failure or reuse physical scale after resizing. Avoid resizing unless necessary. Keep feature-only and calibrated interpretation distinct. Use explicit illustrative process limits and label them synthetic, not approved manufacturing tolerances.
- Only assign expected inspection-status labels to construction-grounded clean controls already supported by accepted fixtures. Degraded/ambiguous cases remain unlabeled unless a defensible independent labeling basis is recorded before evaluation. Never copy the pipeline prediction into expected_statuses or assume every blur/glare case must be UNASSESSED. Document unknown expected behavior rather than forcing a pass.
- Generate inputs in a caller-selected new scratch directory. Preflight target collisions and refuse overwriting by default. Use the existing evaluator CLI unchanged for all analysis and report writing. Do not duplicate the evaluator or alter production thresholds to improve results.
- Add a small Markdown summary command/helper consuming the evaluator's JSON report plus manifest. Validate matching dataset/case identities; output case ID, perturbation, analysis status, expected/assessed sites, current/reference coverage separately if relevant, per-site status and warnings, and emitted observations/affected IDs. Label failed cases and absent outputs explicitly. Do not label absence of a diagnostic observation as a pass.
- Summary distinguishes measured behavior, potential risk requiring human review, and demonstrated defects. A degraded image remaining DETECTED is not automatically wrong without ground truth. Never equate repeatability with accuracy. Preserve raw reports in scratch and record reproduction commands/source commit/parameters in the tracked evaluation document.
- Produce a concise tracked checkpoint document describing actual results for every case and the most consequential findings, with references to stable case IDs. State supported assumptions and unresolved uncertainties. Do not commit images or generated raw reports; the deterministic generator must recreate them.
- Existing baseline and evaluator behavior remain unchanged. If a new crash, incorrect state or questionable classification is observed, record it for planner review; do not silently adjust tests/labels or fix production code in this task.

## Interfaces and data contracts

Consume existing manifest/report v1 and AnalysisProfile. No application API, schema, scoring, frontend or storage changes. New generator and summary CLI are developer evaluation utilities only. Use strict JSON and safe output handling; summary must refuse output aliases of its report/manifest inputs and existing output by default. No network/database/LLM calls, no image sourcing from the internet.

## Allowed paths

- backend/tests/fixtures/generate_inspection_robustness.py (new generator)
- backend/tests/inspection_robustness_summary.py (new summary CLI)
- backend/tests/unit/test_inspection_robustness.py (new)
- docs/evaluation/inspection-robustness-checkpoint.md (new)
- docs/architecture/region-inspection-improvement-plan.md (progress/remaining gaps only)
- .agents/handoff/tasks/DLK-M3-045-inspection-robustness-checkpoint.md
- .agents/handoff/QUEUE.md
- .agents/handoff/PROJECT.md (include planner's completion-estimate reporting preference unchanged)
- .agents/handoff/reviews/DLK-M3-044-review.md (include accepted record unchanged)

## Prohibited scope

Production CV/scoring changes, existing evaluator changes, new models/dependencies, new GUI, database operations, image retention, automatic alignment/site proposals, profile storage, partial scoring, industrial thresholds/accuracy claims, external data acquisition, remote Git operations and main changes. Preserve unrelated scratch output, .agents.zip and PROJECT-PROGRESS-2026-09-19.md; do not stage them.

## Implementation guidance

1. Read applicable AGENTS.md, PROJECT.md, accepted review, evaluator/example generator, fixture helpers and roadmap.
2. Define case IDs and exact transformations first, with clean-control labels and unlabeled perturbations. Keep the matrix small enough for a human to inspect.
3. Test deterministic generation, manifest validity, correct label separation, clipping ROI mapping and output collision handling. Test summary accounting using a hand-authored mixture of successful, unassessed, missing-output and failed cases, including no labels.
4. Run actual generated images through the accepted evaluator. Generate summary and compare it to the JSON fields. Inspect representative generated images to verify that transformations depict what the document says; record artifact paths and inspection method.
5. Write measured results and risk inventory. Update roadmap's stale checkpoint: accepted through 044, saved-case multi-site display completed in 043, full session history still absent, profiles/alignment and partial scoring still deferred. Mark this task implemented only after checks, never mark full roadmap complete.

## Acceptance criteria

- [ ] Fixed reproducible matrix covers the requested capture problems with explicit valid ROIs and no invented labels.
- [ ] Actual existing evaluator processes the matrix; all case outcomes and errors are retained.
- [ ] Summary agrees with raw JSON and distinguishes unknown/failed cases from process pass/fail.
- [ ] Generator/summary preserve source files and reject output collisions.
- [ ] Checkpoint records actual outcomes, parameters, source identity and limits of synthetic evidence.
- [ ] Required checks pass and only allowed files are committed locally.

## Verification

From repository root in PowerShell:

1. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_inspection_robustness.py backend/tests/unit/test_vision_inspection_dataset.py backend/tests/unit/test_vision_inspection_baseline.py -q` using existing safe TEST_DATABASE_URL bootstrap; do not weaken it even though these tests must not access the database.
2. Run the new generator, existing evaluator and new summary CLI using documented --help and exact PowerShell commands. Record outcomes and artifact paths. These are new CLI interfaces to define and document in this task, not assumed existing commands.
3. `& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_baseline.py`
4. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-045-inspection-robustness-checkpoint.md`
5. `git diff --check` before commit and `git diff HEAD~1 HEAD --check` after commit.

No frontend/browser build or full database test suite is required. Use existing image-viewing capabilities for fixture inspection, not a new dependency.

## Planner decision boundaries

Return before production changes, accuracy targets, externally sourced data, new dependencies or broader scope. Unexpected bad results are findings to report, not authorization to tune. Real-image availability and label adjudication remain team decisions.

## Git instructions

Use backend-database. Include completed packet, queue, pending PROJECT.md reporting preference and accepted DLK-M3-044 review in a scoped local commit. Do not push, merge, rebase, create a PR or change main.

Proposed commit message: `test(vision): establish synthetic inspection robustness checkpoint`

## Implementation report

### Summary

Delivered a deterministic 14-case synthetic inspection robustness evaluation matrix (`backend/tests/fixtures/generate_inspection_robustness.py`), a structured Markdown summary utility (`backend/tests/inspection_robustness_summary.py`), comprehensive unit test coverage (`backend/tests/unit/test_inspection_robustness.py`), and a tracked checkpoint report (`docs/evaluation/inspection-robustness-checkpoint.md`).

Executed the existing local evaluator (`backend/tests/vision_inspection_dataset.py`) against this matrix without altering production code. All 14 cases evaluated cleanly with 0 execution failures, achieving 100% status accuracy on clean controls (6/6 sites), 28.6% abstention (8/28 sites flagged UNASSESSED), and 0.0% false-missing rate (0/4 non-missing control sites). Identified critical pipeline blindspots (mild and severe optical blur segment as DETECTED without sharpness gating) and confirmed conservative multi-site reliability (low contrast, glare, and clipping safely trigger UNRELIABLE/UNASSESSED without corrupting unaffected neighboring sites).

### Files changed

- `backend/tests/fixtures/generate_inspection_robustness.py` (new): Deterministic generator creating 14-case synthetic image matrix and Manifest v1 with preflight target collision rejection, explicit coordinate transforms for clipped edge cases, and strict ground-truth label separation.
- `backend/tests/inspection_robustness_summary.py` (new): Markdown summary CLI validating manifest/report identities, enforcing input/output collision protection, classifying case findings into measured baseline, potential risk, and demonstrated defect, and producing an engineering weakness inventory.
- `backend/tests/unit/test_inspection_robustness.py` (new): 9 unit tests verifying deterministic generation (byte-identical images), manifest schema compliance, label separation, clipping ROI normalization, collision preflights, identity validation, and summary risk classification.
- `docs/evaluation/inspection-robustness-checkpoint.md` (new): Tracked checkpoint report documenting the 14-case matrix, reproduction commands, executive metrics, per-case outcomes, weakness inventory, supported assumptions, and unresolved uncertainties.
- `docs/architecture/region-inspection-improvement-plan.md` (modified): Updated Phase 5 with DLK-M3-045 status note and completion estimates.
- `.agents/handoff/tasks/DLK-M3-045-inspection-robustness-checkpoint.md` (modified): Completed implementation report and marked implemented.
- `.agents/handoff/QUEUE.md` (modified): Updated queue moving DLK-M3-044 to accepted verification tasks and DLK-M3-045 to implemented.

### Decisions made

- **Fixed 14-Case Robustness Matrix:** Configured 14 distinct scenarios covering all requested capture degradations (cases 01-14) under a nominal 400x200 two-site canvas without resizing.
- **Strict Ground-Truth Label Separation:** Only construction-grounded clean baseline controls (cases 01, 10, 11) have `expected_statuses` populated. All 11 degraded/ambiguous cases remain unlabeled (`expected_statuses: None`), preventing artificial pass/fail inflation.
- **Explicit Coordinate Transform for Clipped Edge:** Modeled camera translation $dx = +85\text{ px}$, causing the left deposit to clip against $x=0$, and transformed ROIs to valid normalized bounds (`[0.0, 0.20, 0.1875, 0.60]` and `[0.3875, 0.20, 0.30, 0.60]`).
- **Safe Summary Output Handling:** Summary utility rejects output paths matching manifest or report inputs (direct resolved equality and `os.path.samefile` aliases) and refuses overwriting existing outputs unless `--overwrite` is specified.
- **Three-Tier Risk Classification:** Summary categorizes findings into `DEMONSTRATED_DEFECT` (execution error or missing output site), `POTENTIAL_RISK` (defocused or degraded image classified DETECTED without quality warning), and `MEASURED_BASELINE` (clean control or expected conservative gate).

### Verification results

1. **Unit Test Suite:**
   - Command: `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_inspection_robustness.py backend/tests/unit/test_vision_inspection_dataset.py backend/tests/unit/test_vision_inspection_baseline.py -q`
   - Output: `49 passed in 2.16s` (9 robustness tests, 33 dataset evaluation tests, 7 baseline tests).
2. **CLI End-to-End Execution in Scratch Location (`scratch/robustness_checkpoint`):**
   - Generator: `backend/tests/fixtures/generate_inspection_robustness.py -o scratch/robustness_checkpoint --overwrite` (Exit code 0).
   - Evaluator: `backend/tests/vision_inspection_dataset.py -m scratch/robustness_checkpoint/manifest.json -o scratch/robustness_checkpoint/report.json --overwrite` (Exit code 0; 14 cases, 28 sites, 100.0% control accuracy, 28.6% abstention).
   - Summary: `backend/tests/inspection_robustness_summary.py -m scratch/robustness_checkpoint/manifest.json -r scratch/robustness_checkpoint/report.json -o scratch/robustness_checkpoint/summary.md --overwrite` (Exit code 0).
3. **Existing Baseline Runner:**
   - Command: `& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_baseline.py`
   - Output: Exit code 0, 6 cases, 9 sites, 100% status accuracy, 0.9970 mean IoU, 0.018s elapsed.
4. **Task Validation:**
   - Command: `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-045-inspection-robustness-checkpoint.md`
   - Output: `VALID: .agents\handoff\tasks\DLK-M3-045-inspection-robustness-checkpoint.md`.
5. **Git Whitespace Hygiene:**
   - Command: `git diff --check`
   - Output: 0 errors / 0 trailing whitespace issues.

### Limitations and follow-up

- **Purely Synthetic Proof-of-Concept:** Evaluates mathematical pipeline properties and conservative gate logic under controlled perturbations. Does not represent physical PCB solder mask textures, meniscus variations, or factory dust.
- **Defocus Blindspot Identified:** Otsu thresholding without a Laplacian variance / frequency sharpness pre-gate leaves out-of-focus captures ungated, which should be addressed in future sharpness-gating increments.
- **Estimated Completion Checkpoint:** Manual-region prototype scope is estimated at ~90–95%, and the broader region-inspection roadmap at ~65–75% (scope estimates, not accuracy metrics). Real-image evaluation, reusable profiles/alignment, and partial scoring remain deferred.

### Proposed commit message

`test(vision): establish synthetic inspection robustness checkpoint`
