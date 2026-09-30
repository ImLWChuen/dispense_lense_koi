---
task_id: DLK-M3-038
reviewed_commit: 0c65348b80e05cf9ddf88a9ed1ca04967e0fd7b3
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-038

## Decision

Changes still requested after reviewing the correction commit `0c65348`. R1 and R2 are resolved. The required full backend suite has not been rerun against the corrected benchmark and its new test, so the current commit lacks required verification. No production CV change is needed.

## Correction review of 0c65348

- R1 resolved: each case now reports nonnegative descriptive `elapsed_seconds` measured around `_sync_analyze_image`; focused coverage checks the field without a speed target. The documented JSON includes case timings.
- R2 resolved: the report states Python 3.14.0, matching `backend/.venv/pyvenv.cfg`, and uses a direct-script repository-root command that the runner's path setup supports. Gemini reports verifying both CLI variants.
- The correction commit changes benchmark code and adds a seventh focused test. Gemini reports `7 passed` for focused tests and successful CLI runs, but explicitly carries forward the old `577 passed` full-suite result from the initial commit rather than rerunning the full suite after these changes.

## Acceptance evidence

- The fixed manifest has six deterministic synthetic cases and nine labeled sites covering detected, confirmed missing, unassessed, and mixed configurations. Known circle masks are declared from construction parameters, separate from returned outlines.
- The offline runner calls `_sync_analyze_image`, projects actual response statuses/outlines/warnings, rasterizes normalized polygons at full-image dimensions, and reports status confusion, abstention, false missing, outline availability, and IoU with explicit denominators. The output and documentation clearly limit conclusions to synthetic cases.
- Unit tests exercise metric math with deliberately incorrect predictions, false missing, absent outlines, empty denominators, and polygon overlap. The smoke test runs the real pipeline and checks the mixed-case conservative gate.
- Gemini reports 6 focused tests and 577 full backend tests passed, the CLI ran successfully, task validation was `VALID`, and whitespace validation passed. Under the planner/reviewer role split, I inspected code and tests but did not rerun them. The committed diff passes the whitespace check.
- The commit changes only task-allowed test support, docs, and handoff files; unrelated untracked files were not committed.

## Findings

### R1 — P2: Per-case elapsed time is absent

Location: `backend/tests/vision_inspection_baseline.py`, `run_vision_inspection_baseline` around the case loop and `per_case_results` construction.

The task's output contract requires elapsed time in each bounded case result, but the runner measures and emits only one overall `elapsed_seconds`. Add a descriptive `elapsed_seconds` for each case using `time.perf_counter()` around that case's analysis (state clearly what the interval covers). Test that every case has a numeric nonnegative value; do not assert a performance target. Regenerate the documented JSON from an actual run and update the implementation report. Timing must remain descriptive, not a quality claim.

### R2 — P2: Reproduction instructions misstate the environment and root command

Location: `docs/evaluation/region-inspection-synthetic-baseline.md`, “Reproduction Command” and “Runtime Environment.”

The document says the backend virtual environment uses Python 3.12, while `backend/.venv/pyvenv.cfg` identifies Python **3.14.0**. It also instructs running `-m tests.vision_inspection_baseline` from repository root; the `tests` package lives under `backend/` and `backend/pyproject.toml` packages only `app*`, so that command is not a portable root-directory invocation. Correct the observed version, keep the valid `backend/` command, and either remove the root variant or replace it with a working direct-script path. Gemini should verify any retained root variant before documenting it.

## Follow-up

### R3 — P2: Required full backend suite was not rerun after the correction

Location: `.agents/handoff/tasks/DLK-M3-038-synthetic-region-inspection-baseline.md`, “Verification results.”

The packet requires a full backend check, and the corrected code is part of that suite. The report says `577 passed` from before R1/R2 changes while a seventh focused test now exists, so that result cannot verify the current commit. Run the full backend suite against the current code using the existing safe disposable test database, record the actual count/outcome, and update the task report and queue. If it fails, fix only the relevant test-support issue and rerun affected checks. Do not change production CV behavior or fixture labels.

No next feature task or remote Git operation is authorized.
