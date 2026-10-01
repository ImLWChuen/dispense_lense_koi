---
task_id: DLK-M3-044
title: Evaluate local image sets without changing inspection behavior
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-043]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-044: Local image evaluation runner

## Objective

Provide a repeatable offline way to evaluate a team-supplied local image set with the existing region-inspection pipeline, inspect per-site results and identify failures. Enable representative-image evaluation without claiming that a representative dataset or trustworthy labels are already available. Deliver evaluation tooling and a team runbook, not segmentation tuning.

## Current evidence

- DLK-M3-043 accepted at 41d7351d7e4165fc95b17de707fe22887c654aa7. Its accepted review and queue updates are pending planner artifacts.
- backend/tests/vision_inspection_baseline.py runs six generated synthetic scenarios through _sync_analyze_image, with per-site status metrics and construction-grounded outline IoU. It accepts no external dataset manifest.
- docs/evaluation/region-inspection-synthetic-baseline.md records this baseline and capture assumptions. Synthetic results do not establish factory-image accuracy.
- Region workbench, saved scalar evidence and JSON/PDF reports are delivered. Real-image evaluation, reusable profiles/alignment and partial score-bearing evidence remain separate roadmap gaps.
- No curated representative local dataset or independently reviewed real-image labels have been established for this task. Do not invent either or scrape images to fill the gap.

## Requirements

- Add a standalone CLI accepting a versioned JSON manifest, dataset root and explicit output report path. Use existing Python/OpenCV/Pydantic dependencies and the actual existing synchronous analysis pipeline. No running web server, network requests, database session or LLM is required for the CLI.
- Manifest v1 contains dataset ID, origin (synthetic or real), case IDs, current image relative path, optional reference image relative path, the existing AnalysisProfile object, optional per-ROI expected inspection statuses, and label provenance/reviewer notes when labels are supplied. Validate unique case IDs, valid profile/unique expected ROI IDs, and label keys belonging to configured ROIs. Accept missing labels as unlabeled; never use model predictions as ground truth.
- Validate schema/profile before running. Restrict image paths to existing files under the explicitly selected dataset root after resolution, rejecting absolute paths and escape through traversal or links. Respect existing pipeline image-size/decode limits. Do not print credentials, file contents or private absolute paths in reports. No downloading or image copying into the repository.
- Write a versioned JSON report with dataset/case IDs, origin, run provenance (source commit when obtainable, relevant runtime versions), explicit profile/limits, per-case elapsed time, analysis status, current/reference coverage separately, per-site predicted status/measurements/warnings, affected-region observations and optional supplied labels. Preserve current whole-image gates; report their effects rather than relaxing them. No pass/fail process claim without recorded limits.
- Expected sites omitted by pipeline output must be recorded as missing output, not silently excluded or fabricated as MISSING. Decode/analysis failures must have explicit per-case error records and counts; continue remaining cases. Separate input/schema failures from successful runs with case failures and document exit codes. Write no apparently complete success report after a fatal validation failure.
- Aggregate labeled site confusion counts, correct/incorrect counts, unlabeled counts, missing-output counts and failed-case counts. Define denominators explicitly: status accuracy must not improve by dropping failed/missing predictions; include labeled sites in failed cases in eligible total and show failure accounting outside the three-status confusion matrix. Zero eligible labels yields null accuracy, never 0% or 100%. Report prediction abstention as UNASSESSED among emitted predictions, distinct from execution errors. Report false-missing count and denominator explicitly (known non-MISSING labels). Do not mix synthetic and real datasets or present exploratory/unreviewed labels as manufacturing validation.
- No external outline IoU in this increment: external ground-truth masks/contours are not part of manifest v1. Preserve the existing synthetic outline benchmark unchanged. Label external boundary accuracy as not evaluated.
- Supply a small example manifest and an explicit generator command/helper that creates its synthetic images in a user-selected scratch directory using existing fixture helpers. Include detected, confirmed missing and unassessed/mixed cases plus at least one unlabeled site. Inputs/outputs remain outside tracked source. A generated sample demonstrates runner operation only.
- Document PowerShell commands, expected report structure, file/label provenance, capture notes (lighting, focus, scale, viewpoint/material), independent annotation before inspecting predictions, and how to record a disagreement for later review. Real images remain user-supplied. Define a small worksheet for image ID, permitted use/source, capture notes, ROI assumptions, label/reviewer, prediction and adjudication; keep expected labels separate from predictions.
- Do not select production accuracy thresholds, claim representative accuracy, or tune algorithm parameters based on sample outcomes. Summarize unresolved evaluation decisions and any observed pipeline failures without expanding into fixes.

## Interfaces and data contracts

New offline manifest/report format v1 only. Reuse existing AnalysisProfile and analysis response; no public API, database, frontend or diagnostic interface changes. The runner reads local files and writes only its requested report. Refuse overwriting an existing report by default; an explicit --overwrite flag may authorize replacing that report only, never source images or manifest. Serialize strictly valid JSON (no NaN/Infinity). Keep generated labels and real annotations traceable to their distinct origins.

## Allowed paths

- backend/tests/vision_inspection_dataset.py (new CLI and reusable evaluator)
- backend/tests/unit/test_vision_inspection_dataset.py (new)
- backend/tests/fixtures/local_image_evaluation_example.json (new synthetic manifest)
- backend/tests/fixtures/generate_local_image_evaluation.py (new generator)
- docs/evaluation/local-image-evaluation.md (new runbook and worksheet)
- docs/architecture/region-inspection-improvement-plan.md (progress only)
- .agents/handoff/tasks/DLK-M3-044-local-image-evaluation.md
- .agents/handoff/QUEUE.md
- .agents/handoff/reviews/DLK-M3-043-review.md (include accepted planner record unchanged)

## Prohibited scope

Production pipeline/threshold changes, new models/dependencies, database writes/schema changes, frontend work, reusable production profiles, image retention in the application, partial evidence scoring, external image collection, industrial-accuracy claims, new outline metrics, remote Git operations or main changes. Preserve .agents.zip and PROJECT-PROGRESS-2026-09-19.md. Never commit private images, generated reports, credentials or environment files.

## Implementation guidance

1. Read applicable instructions, PROJECT.md, accepted review, existing synthetic evaluator/tests and image API/schema guards. Keep the existing baseline unmodified.
2. Implement the smallest strict manifest loader and offline runner around the existing pipeline; separate summary calculation from analysis so accounting can be tested independently.
3. Test hand-calculated mixtures of correct, incorrect, unlabeled, missing-output and failed cases. Include reference image forwarding, malformed schema, duplicate IDs, invalid ROI labels, file/path failures and safe output handling.
4. Generate sample files in a new scratch directory and run the actual CLI end to end. Compare the sample output to declared expectations, and run an unlabeled variant demonstrating null accuracy. Intentionally exercise a corrupt-image case and document partial-run error behavior.
5. Complete runbook, worksheet, progress notes and implementation report. State representative real-image evaluation is still pending unless user-supplied evidence actually exists. Commit scoped files locally.

## Acceptance criteria

- [x] Actual pipeline evaluates local current/reference images using supplied profiles without network/server/database access.
- [x] Manifest/path validation and output protection prevent accidental input escape or overwrite.
- [x] Per-case/per-site outputs, limits, labels and errors are traceable and strict JSON.
- [x] Hand-calculated tests establish honest denominators, null unlabeled accuracy and explicit missing/failed accounting.
- [x] Synthetic sample CLI and unlabeled/error runs are reproducible from documented PowerShell commands.
- [x] Existing synthetic baseline remains unchanged; no external boundary/industrial accuracy claim.
- [x] All required checks recorded and only allowed files committed locally.

## Verification

From repository root in PowerShell:

1. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_inspection_dataset.py backend/tests/unit/test_vision_inspection_baseline.py -q` using the existing safe test environment. Pytest bootstrap may require TEST_DATABASE_URL even though these tests must not access the database; do not weaken bootstrap.
2. `& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_baseline.py`
3. Run the new generator and CLI with their documented --help and sample commands, including an unlabeled dataset and one corrupt file. Record exact invocations, exit codes, sample result counts and scratch locations. Confirm CLI operation without a running backend or DB connection; do not stop other people's running services to prove this.
4. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-044-local-image-evaluation.md`
5. `git diff --check`

No frontend build/browser checks or full database suite are required for this isolated evaluation tooling. If production files must change, stop and return to planner.

## Planner decision boundaries

Return before new dependencies, production tuning, storage, external data acquisition, dataset licensing decisions, accuracy targets or broader scope. Lack of real images does not block the tool increment; it blocks any claim of real-world validation. Do not invent labels or datasets.

## Git instructions

Work on backend-database. Include this packet, queue and pending accepted DLK-M3-043 review in the local implementation commit. Do not push, merge, rebase, create a PR or change main.

Proposed commit message: `test(vision): add local image dataset evaluation runner`

## Implementation report

### Summary

Delivered a standalone, offline, manifest-driven local image dataset evaluation runner and reporting CLI (`backend/tests/vision_inspection_dataset.py`), Manifest v1 specification (`DatasetManifest`), synthetic sample fixture generator (`backend/tests/fixtures/generate_local_image_evaluation.py`), static template fixture (`backend/tests/fixtures/local_image_evaluation_example.json`), and comprehensive team evaluation runbook and worksheet (`docs/evaluation/local-image-evaluation.md`).

The evaluator executes against the existing synchronous vision inspection pipeline (`_sync_analyze_image`) using standard `AnalysisProfile` specifications, without requiring a running web server, active database session, network access, or LLM services. It enforces path containment security, honest un-inflated metric denominators (including failed cases and missing pipeline output in eligible totals, null accuracy for unlabeled datasets, distinct abstention and false-missing rates), strict JSON serialization with `allow_nan=False`, and default report overwrite protection. Production CV services, database schemas, scoring logic, and UI code remain completely untouched. No representative real-world dataset or manufacturing accuracy claims are made.

### Files changed

- `backend/tests/vision_inspection_dataset.py` (new): Standalone CLI and reusable evaluation runner supporting Manifest v1, strict path containment, per-case timing/continuation, honest metrics computation, and strict JSON output formatting.
- `backend/tests/unit/test_vision_inspection_dataset.py` (new): 11 unit tests covering hand-calculated metrics accounting, null unlabeled accuracy, duplicate case ID rejection, unknown label ROI rejection, missing reference path rejection, path traversal rejection, end-to-end synthetic evaluation, corrupt-image error containment, CLI overwrite protection, and fatal schema error handling.
- `backend/tests/fixtures/generate_local_image_evaluation.py` (new): Synthetic image and manifest generator producing multi-scenario fixtures (clean detected, confirmed missing, uniform unassessed, mixed two-site with unlabeled ROI, dual-image reference comparison, and optional corrupt image).
- `backend/tests/fixtures/local_image_evaluation_example.json` (new): Static template manifest demonstrating Manifest v1 schema, fields, profiles, limits, and label provenance.
- `docs/evaluation/local-image-evaluation.md` (new): Runbook and worksheet covering manifest specifications, path containment rules, CLI usage, PowerShell commands, exit codes, blind labeling guidelines, adjudication workflow, evaluation worksheet template, and unresolved roadmap decisions.
- `docs/architecture/region-inspection-improvement-plan.md` (modified): Updated progress checkpoint table and added Phase 5 Increment DLK-M3-044 status record.
- `.agents/handoff/tasks/DLK-M3-044-local-image-evaluation.md` (modified): Updated task status to implemented and recorded verification evidence.
- `.agents/handoff/QUEUE.md` (modified): Updated task queue to record accepted DLK-M3-043 and active DLK-M3-044 in_progress/implemented.
- `.agents/handoff/reviews/DLK-M3-043-review.md` (unchanged): Retained pending accepted planner review record for local commit inclusion.

### Decisions made

- **Manifest v1 Schema & Semantics:** Built using Pydantic v2 models (`DatasetManifest`, `ManifestCase`). Validates unique case IDs, relative image paths, required reference paths in `REFERENCE_IMAGE` mode, and restricts label keys strictly to configured `roi_id` values in `profile.rois`. Accepts missing ROI keys as unlabeled without fabricating expectations or using predictions as ground truth.
- **Path Containment & Security:** Enforced strict relative paths and containment under `--dataset-root` (or manifest directory). Rejects leading slashes, drive letters, and directory traversal (`..`) using `target.resolve().relative_to(root.resolve())`. Rejects missing files, non-files, and files exceeding the 10 MB payload ceiling. Suppresses private host filesystem paths in error messages and output reports.
- **Honest Denominators & Failure Accounting:** The eligible labeled sites total includes all sites with ground-truth labels across all cases, regardless of whether a case experienced an execution/decode error or the pipeline omitted measurements. Failed cases and omitted measurements are counted as incorrect in status accuracy, preventing accuracy inflation. When 0 eligible labeled sites exist, status accuracy is explicitly `null` (None), never 0% or 100%.
- **Abstention & False-Missing Rates:** Abstention rate is computed strictly among emitted predictions (`predicted_status == "UNASSESSED"`). False-missing rate is evaluated over known non-`MISSING` ground truth (`expected_status in ["DETECTED", "UNASSESSED"]` where `predicted_status == "MISSING"`), providing an explicit safety metric.
- **External Boundary Benchmark Label:** Explicitly recorded in reports and runbook as `{"status": "not_evaluated", "reason": "External ground-truth masks or contours are not part of manifest v1."}`, preserving the separate synthetic outline benchmark unchanged.
- **Report Overwrite Protection:** The runner refuses to overwrite an existing report by default (exit code 1), requiring an explicit `--overwrite` flag.
- **Strict JSON Serialization:** Uses `json.dumps(..., allow_nan=False)` to guarantee valid standard JSON without `NaN` or `Infinity`.

### Verification results

1. **Unit Test Suite:**
   - Command: `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_inspection_dataset.py backend/tests/unit/test_vision_inspection_baseline.py -q`
   - Output: `18 passed in 0.93s` (11 new dataset evaluation tests + 7 existing baseline tests).
2. **Existing Baseline Runner:**
   - Command: `& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_baseline.py`
   - Output: Exit code 0, 6 cases, 9 sites, 100% status accuracy, 0.9970 mean IoU, 0.0167s elapsed, unchanged output structure.
3. **Generator and CLI Verification in Scratch Locations:**
   - Standard Labeled Dataset:
     - Invocations:
       - `& .\backend\.venv\Scripts\python.exe backend/tests/fixtures/generate_local_image_evaluation.py -o scratch/local_eval_demo/labeled` (Exit code 0)
       - `& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_dataset.py -m scratch/local_eval_demo/labeled/manifest.json -o scratch/local_eval_demo/labeled/report.json` (Exit code 0)
     - Results: 5 total cases (5 success, 0 failed), 6 total sites (5 labeled, 1 unlabeled), Status Accuracy: 100.0% (5/5), Report: `scratch/local_eval_demo/labeled/report.json`.
   - Overwrite Protection Check:
     - Re-run without `--overwrite`: `Fatal error: Output report '...' already exists. Use --overwrite to replace it.` (Exit code 1).
     - Re-run with `--overwrite`: Exit code 0, replaced report cleanly.
   - All-Unlabeled Dataset:
     - Invocations:
       - `& .\backend\.venv\Scripts\python.exe backend/tests/fixtures/generate_local_image_evaluation.py -o scratch/local_eval_demo/unlabeled --all-unlabeled` (Exit code 0)
       - `& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_dataset.py -m scratch/local_eval_demo/unlabeled/manifest_unlabeled.json -o scratch/local_eval_demo/unlabeled/report.json` (Exit code 0)
     - Results: 5 total cases (5 success, 0 failed), 6 total sites (0 labeled, 6 unlabeled), Status Accuracy: `null` (no labels).
   - Corrupt Image Dataset (Error Containment):
     - Invocations:
       - `& .\backend\.venv\Scripts\python.exe backend/tests/fixtures/generate_local_image_evaluation.py -o scratch/local_eval_demo/corrupt --include-corrupt` (Exit code 0)
       - `& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_dataset.py -m scratch/local_eval_demo/corrupt/manifest.json -o scratch/local_eval_demo/corrupt/report.json` (Exit code 0)
     - Results: 6 total cases (5 success, 1 failed with `ImageValidationError`), 7 total sites (6 labeled, 1 unlabeled), Status Accuracy: 83.3% (5/6). Corrupt case properly penalized without crashing runner or dropping from denominator.
4. **Task Validation:**
   - Command: `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-044-local-image-evaluation.md`
   - Output: `VALID: .agents\handoff\tasks\DLK-M3-044-local-image-evaluation.md`.
5. **Git Whitespace Hygiene:**
   - Command: `git diff --check`
   - Output: 0 errors / 0 trailing whitespace issues.

### Limitations and follow-up

- Representative factory images with multi-technician ground truth remain user-supplied and are not part of this repository increment.
- External polygon/contour ground-truth masks are deferred to manifest format v2; outline accuracy on external datasets is explicitly labeled as not evaluated.
- Automated board alignment, template fiducial registration, and persistent template database storage remain separate roadmap gaps.

### Proposed commit message

`test(vision): add local image dataset evaluation runner`
