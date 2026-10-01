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

Following review `DLK-M3-044-review.md` and subsequent follow-up findings, resolved corrections:
- **R1 Follow-Up (Enforce No-Overwrite at Final Publication):** Implemented `publish_report_file` to enforce strict no-clobber behavior at final report publication when `--overwrite` is omitted. If the destination report exists (or appears concurrently during evaluation), publication raises `FileExistsError`, exits with code 1, leaves the existing destination byte-identical, and cleans up all temporary `.tmp_*` files. Kept atomic replacement only for explicit `--overwrite`. Added deterministic unit test with sentinel destination created during mocked evaluation.
- **R2 (Profile & Provenance Preservation):** Persisted the complete `AnalysisProfile` (mode, ROI coordinates, scale, limits), case `notes`, safe relative image paths, and `label_provenance` / `label_provenance_status` (`provided`, `inherited`, `unreviewed`, `unlabeled`) across both success and error records. When labels lack case or dataset provenance, visibly flagged as unreviewed and tracked in summary. Structured explicit `current_inspection_coverage` and `reference_inspection_coverage` summaries (status, expected/assessed counts, unassessed/missing ROI IDs), separate from material coverage ratios.
- **R3 Follow-Up (Replace Raw Exception Text with Safe Public Messages):** Replaced raw exception strings with fixed, informative public messages across `evaluate_dataset` (`IMAGE_VALIDATION`, `PATH_VALIDATION`, `FILESYSTEM_ACCESS`, `EXECUTION_ERROR`) including case ID and safe failure reason without echoing `str(exc)`. Implemented `format_safe_schema_error` to format structured Pydantic error field locations and error types without raw input values. Guarded CLI preflight filesystem operations against `OSError` / `RuntimeError` returning a sanitized exit-1 diagnostic without tracebacks or host paths. Enhanced `sanitize_error_message` regexes to cover Windows slash and backslash paths with spaces, UNC network paths (`\\...` and `//...`), and `/mnt` paths. Added regression tests asserting private path fragments are completely absent from report JSON and captured diagnostics.

The evaluator executes against the existing synchronous vision inspection pipeline (`_sync_analyze_image`) using standard `AnalysisProfile` specifications, without requiring a running web server, active database session, network access, or LLM services. Production CV services, database schemas, scoring logic, and UI code remain completely untouched. No representative real-world dataset or manufacturing accuracy claims are made.

### Files changed

- `backend/tests/vision_inspection_dataset.py` (modified): Standalone CLI and reusable evaluation runner supporting Manifest v1, input protection against manifest/image overwrite (direct and alias/samefile), atomic no-clobber report publication, preflight path traversal and filesystem access containment, sanitized safe error messages, structured schema validation formatting without input echoing, full AnalysisProfile preservation, separate current/reference inspection coverage summaries, and honest denominator metrics.
- `backend/tests/unit/test_vision_inspection_dataset.py` (modified): 29 unit tests (36 total across module including baseline) covering final publication sentinel no-clobber, error sanitization for slash/backslash paths with spaces, UNC and /mnt paths, absolute-path schema rejection without private fragment leakage, preflight filesystem error handling without tracebacks, per-case error path suppression, input overwrite rejection for manifest/images/aliases, generator collision preflighting, full profile and provenance preservation in success/error cases, separate inspection coverage summaries, unreviewed provenance flagging, traversal preflight, hand-calculated metrics accounting, null unlabeled accuracy, and schema validation.
- `backend/tests/fixtures/generate_local_image_evaluation.py` (modified): Preflight target collision checks before disk writes and `--overwrite` CLI flag.
- `backend/tests/fixtures/local_image_evaluation_example.json` (created): Static template manifest demonstrating Manifest v1 schema, fields, profiles, limits, and label provenance.
- `docs/evaluation/local-image-evaluation.md` (modified): Updated runbook and worksheet covering protected input guarantees, atomic no-clobber report publication, complete report schema with profile and separate coverage summaries, sanitized path privacy, exact exit codes, and clean whitespace.
- `docs/architecture/region-inspection-improvement-plan.md` (modified): Updated progress checkpoint table and Phase 5 Increment DLK-M3-044 status record.
- `.agents/handoff/tasks/DLK-M3-044-local-image-evaluation.md` (modified): Updated implementation report with R1 and R3 follow-up resolutions and verification evidence.
- `.agents/handoff/QUEUE.md` (modified): Updated task queue to record accepted DLK-M3-043 and implemented DLK-M3-044 with resolved review findings.
- `.agents/handoff/reviews/DLK-M3-044-review.md` (included): Maintained reviewer review record for local commit inclusion.

### Decisions made

- **Final Publication No-Clobber Semantics (R1 Follow-Up):** In `publish_report_file`, when `--overwrite` is False, the runner verifies destination nonexistence and uses atomic no-replace publication (`os.rename` on Windows, `os.link` + `unlink` on POSIX). If the file exists or appears during execution, `FileExistsError` is raised, destination remains untouched, temporary files are unlinked, and CLI returns exit code 1.
- **Safe Public Messages Over Regex Path Expansion (R3 Follow-Up):** Rather than attempting to redact arbitrary exception strings after the fact, errors in `evaluate_dataset` are mapped to fixed public diagnostic messages with `case.case_id` and safe error category. Raw `str(exc)` from `OSError` or `PermissionError` is never serialized into report `error.message` or `case_warnings`.
- **Structured Schema Error Formatting (R3 Follow-Up):** Pydantic validation errors are parsed via `format_safe_schema_error`, formatting field locations (`cases -> 0 -> current_image_path`) and error types without accessing `err['input']` or printing raw input paths.
- **Preflight Resolution Guarding (R3 Follow-Up):** All CLI argument resolutions and preflight filesystem accesses (`resolve()`, `exists()`, `is_file()`, `is_dir()`) are guarded against `OSError` and `RuntimeError`, outputting a clean diagnostic without tracebacks.
- **Input Overwrite Protection (R1):** The runner preflights the output report path against the manifest and all case current/reference image paths using resolved path equality and `os.path.samefile` alias checks. Target collision with any evaluation input is rejected with exit code 1, regardless of whether `--overwrite` was specified.
- **Generator Target Collision Preflight (R1):** The synthetic fixture generator checks if target image files or manifest exist in `output_dir` before initiating generation. Refuses execution by default (raising `FileExistsError` / exit code 1) unless authorized via `--overwrite`.
- **Full Profile & Context Preservation (R2):** Persisted the complete validated `AnalysisProfile` (including ROI coordinates, dimensions, mode, `mm_per_pixel`, and process/reference limits) in every case record (both `SUCCESS` and `ERROR`). Preserved case `notes`, safe relative image paths, and `label_provenance`.
- **Label Provenance Status Tracking (R2):** If labels are provided, tracks provenance as `provided` (from case), `inherited` (from dataset), or `unreviewed` (when neither is provided). Unreviewed cases are visibly flagged in `label_provenance`, tracked in `summary.case_counts.unreviewed_labeled_cases`, and appended to `case_warnings`.
- **Separate Current and Reference Inspection Coverage (R2):** Replaced scalar-only coverage summaries with distinct `current_coverage_ratio` / `reference_coverage_ratio` (material coverage floats) and `current_inspection_coverage` / `reference_inspection_coverage` (objects containing status, expected_roi_count, assessed_roi_count, unassessed_roi_ids, and missing_roi_ids).
- **Fatal vs Per-Case Error Semantics (R3):** Manifest syntax, schema validation, path traversal escape (`..`), protected input collisions, and preflight filesystem errors are fatal preflight failures (Exit code 1, no report written). Image decode/validation failures within valid paths are caught per case, allowing partial run completion with explicit case error records (Exit code 0).

### Verification results

1. **Unit Test Suite:**
   - Command: `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_vision_inspection_dataset.py backend/tests/unit/test_vision_inspection_baseline.py -q`
   - Output: `36 passed in 1.27s` (29 dataset evaluation tests + 7 baseline tests).
2. **Existing Baseline Runner:**
   - Command: `& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_baseline.py`
   - Output: Exit code 0, 6 cases, 9 sites, 100% status accuracy, 0.9970 mean IoU, 0.0221s elapsed, unchanged output structure.
3. **Generator and CLI Verification in Scratch Locations:**
   - **Standard Labeled Dataset (`scratch/local_eval_demo/labeled`):**
     - Generator: `backend/tests/fixtures/generate_local_image_evaluation.py -o scratch/local_eval_demo/labeled --overwrite` (Exit code 0).
     - Generator Collision Check without `--overwrite`: `Error generating synthetic dataset: Target file already exists: 'manifest.json'. Use --overwrite to authorize replacing existing files.` (Exit code 1).
     - Runner: `backend/tests/vision_inspection_dataset.py -m scratch/local_eval_demo/labeled/manifest.json -o scratch/local_eval_demo/labeled/report.json --overwrite` (Exit code 0).
     - Results: 5 total cases (5 success, 0 failed), 6 total sites (5 labeled, 1 unlabeled), Status Accuracy: 100.0% (5/5). Report includes full profiles, notes, provenance, and separate coverage summaries.
   - **Input Overwrite Protection Check (R1):**
     - Targeting manifest with `--overwrite`: `Fatal error: Output path cannot overwrite evaluation inputs (manifest or source images). Target path matches a protected evaluation input: 'manifest.json'` (Exit code 1).
     - Targeting source image with `--overwrite`: `Fatal error: Output path cannot overwrite evaluation inputs (manifest or source images). Target path matches a protected evaluation input: 'case_01_detected.png'` (Exit code 1).
     - Both input files remained byte-identical.
   - **All-Unlabeled Dataset (`scratch/local_eval_demo/unlabeled`):**
     - Generator: Exit code 0 with `--all-unlabeled --overwrite`.
     - Runner: Exit code 0 with `--overwrite`.
     - Results: 5 total cases (5 success, 0 failed), 6 total sites (0 labeled, 6 unlabeled), Status Accuracy: `null` (no labels).
   - **Corrupt Image Dataset (`scratch/local_eval_demo/corrupt`):**
     - Generator: Exit code 0 with `--include-corrupt --overwrite`.
     - Runner: Exit code 0 with `--overwrite`.
     - Results: 6 total cases (5 success, 1 failed with `ImageValidationError`), 7 total sites (6 labeled, 1 unlabeled), Status Accuracy: 83.3% (5/6). Corrupt case preserved full profile, notes, and provenance with sanitized error category `IMAGE_VALIDATION`.
4. **Task Validation:**
   - Command: `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-044-local-image-evaluation.md`
   - Output: `VALID: .agents\handoff\tasks\DLK-M3-044-local-image-evaluation.md`.
5. **Git Whitespace Hygiene:**
   - Command: `git diff --check`
   - Output: 0 errors / 0 trailing whitespace issues.
   - Command: `git diff --check HEAD~1 docs/evaluation/local-image-evaluation.md`
   - Output: 0 errors / 0 trailing whitespace issues.

### Limitations and follow-up

- Representative factory images with multi-technician ground truth remain user-supplied and are not part of this repository increment.
- External polygon/contour ground-truth masks are deferred to manifest format v2; outline accuracy on external datasets is explicitly labeled as not evaluated.
- Automated board alignment, template fiducial registration, and persistent template database storage remain separate roadmap gaps.

### Proposed commit message

`test(vision): resolve DLK-M3-044 review findings for local image evaluation runner`
