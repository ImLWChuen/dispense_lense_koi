---
task_id: DLK-M3-044
reviewed_commit: 2f27c1922cff29485f87be4b0166f66de7cf6ae5
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-044

## Decision

Follow-up at 2f27c1922cff29485f87be4b0166f66de7cf6ae5: Windows no-replace publication and fixed per-case filesystem/execution messages are corrected. R2 remains resolved. Gemini reports 36 focused tests passing and the existing sample runs; reviewer inspected code and did not rerun tests. Committed whitespace check passes. Two remaining code paths prevent acceptance:

- **R1 remaining (P2):** publish_report_file's POSIX branch catches OSError/NotImplementedError from os.link and falls back to exists() followed by shutil.move(). This recreates the no-overwrite race when hardlinks are unsupported: a destination appearing after the check can be replaced by move. The temp file is already in the destination directory, so no cross-device fallback is needed. Fail closed with a safe unsupported-publication diagnostic rather than falling back to an overwriting primitive. Test simulated link failure and prove a destination sentinel remains unchanged; retain the Windows behavior.
- **R3 remaining (P2):** format_safe_schema_error still emits err['msg'] and raw string location components. Existing validators interpolate unknown ROI IDs, configured IDs, case IDs and duplicate IDs into their messages. An invalid expected_statuses key such as C:/private/customer/file, or a duplicate case ID with that value, therefore still appears in stderr; removing err['input'] does not sanitize custom messages. Dict keys/extra fields also enter Pydantic error locations. Render only allowlisted schema-field segments plus numeric indices, safe placeholders for dynamic keys, and a fixed explanation based on error type. Do not echo arbitrary validator messages. Add captured-CLI regressions for unknown ROI labels, duplicate case IDs and extra-field/dict keys containing private path markers. Preserve actionable schema locations without exposing values.

These are the only requested follow-up changes. Continue DLK-M3-044, rerun focused tests, validate and update the report, then commit locally without push/PR/merge.

## Previous follow-up at d1f66de

Follow-up at d1f66de2e1cb821614a306a3f159f840fe8d5af9: R2 is resolved; R1 direct/alias input protection and generator default collisions are fixed; exit documentation and whitespace are corrected. Gemini reports 26 focused tests passing and repeated sample CLI runs. Reviewer inspected changes without rerunning tests. Two bounded corrections remain before acceptance.

### R1 follow-up — P2: Enforce no-overwrite at final publication

main checks output_path.exists() before evaluating the dataset, then always calls temp_path.replace(output_path), even without --overwrite. If another run/user creates the output during evaluation, this unconditionally replaces that file despite no overwrite authorization. Atomic replacement prevents partial writes but does not enforce no-clobber behavior. Use a final publication mechanism that fails atomically when the destination exists in the no-overwrite branch; keep replacement only for explicit --overwrite. Add a deterministic test that creates a sentinel destination during a mocked evaluation, then verifies nonzero exit and byte-identical sentinel. Preserve input alias checks and clean up temporary files.

### R3 follow-up — P2: Replace raw error text with safe public messages

sanitize_error_message still depends on incomplete path regexes: C:/private/model/file is untouched, UNC paths are untouched, C:\\Users\\Kee Chun Shang\\private.txt leaves its suffix after the first space, and /mnt/private/file is not covered. More importantly manifest JSON/schema handlers still write raw exc text without this sanitizer; Pydantic errors can echo the full supplied absolute path/input. Preflight resolve/OSError failures are not consistently caught. The claim that all errors are sanitized is therefore not supported.

Use fixed public messages/categories for unexpected filesystem/execution errors, with case ID and safe field location where useful. For schema errors, format structured error locations/types without input values or raw exception strings. Catch resolution/preflight filesystem failures at the CLI boundary so they produce a sanitized exit-1 diagnostic, not a traceback. Do not try to solve arbitrary exception privacy by expanding a list of path prefixes. Add regression cases for slash/backslash Windows paths with spaces, UNC and /mnt paths, plus absolute-path schema rejection and preflight OSError; assert private fragments are absent from both report JSON and captured diagnostics. Keep useful known image/path error categories without leaking raw text.

Continue this task, update report and queue to implemented only after corrections/checks, and commit locally including the review. No new task packet or production changes. R2 does not need reimplementation.

## Historical initial findings

Changes requested. The offline pipeline integration and denominator accounting are useful and in scope. Gemini reports 18 focused tests passing, unchanged synthetic baseline and labeled/unlabeled/corrupt CLI runs. Reviewer inspected source and reported results without rerunning tests. Untracked scratch output exists; preserve it and do not stage it. No push or merge.

## R1 — P1: Prevent report output from overwriting evaluation inputs

backend/tests/vision_inspection_dataset.py main checks only whether the output exists and --overwrite is present before write_text. Consequently --output manifest.json --overwrite replaces the manifest with a report; selecting a current/reference image does the same to source image bytes. The task explicitly limits overwrite permission to reports, never inputs. Resolved symlinks and hardlinks need the same protection. The generator also writes fixed image/manifest names into an existing directory without collision protection.

Before evaluation/writing, reject output aliases of the manifest and all current/reference inputs regardless of --overwrite (resolved equality and existing-file identity). Enforce no-clobber creation without overwrite and preferably atomic report replacement after successful serialization. Preflight generator target collisions before any writes and refuse existing files by default. Add CLI tests proving manifest/current/reference files remain byte-identical for direct and supported alias collisions, plus default report and generator collision tests. Do not execute destructive tests against actual user inputs.

## R2 — P2: Preserve reproducible profile and annotation context in reports

evaluate_dataset records only process/reference limits, omitting the actual AnalysisProfile (mode, ROI coordinates, scale and other settings). Per-case label_provenance and notes are accepted by the manifest but dropped from output. Failed cases drop even limits. Reference coverage is reduced to mean deposit coverage, with no separate reference inspection-coverage status/counts. Thus a report cannot establish the configuration/annotation used or distinguish complete current coverage from unassessed reference coverage without its original manifest.

Persist the validated profile and per-case annotation provenance/notes in success AND error records, alongside safe relative image identifiers. Include explicitly named current/reference inspection coverage summaries (status, expected/assessed counts and relevant IDs), separate from material coverage ratios. When labels are supplied require meaningful case-level or inherited dataset provenance, or visibly flag missing/unreviewed provenance; never silently imply independent validation. Add tests using different profiles, case provenance, a failing case and an unassessed reference to assert these fields survive unchanged and separate.

## R3 — P2: Sanitize filesystem errors and align failure documentation

evaluate_dataset serializes str(exc) into error.message and case_warnings. A PermissionError/OSError from read_bytes/stat/resolve can contain an absolute local path, despite the report claiming path suppression. CLI fatal handlers likewise print raw exception/validation text, potentially including full input values. Use stable safe error categories/messages and safe case/relative identifiers; do not echo raw exception text into reports. Add a simulated OSError containing a private path and assert its absence from report JSON and user-facing diagnostics.

The CLI help calls missing files/path traversal fatal exit-1 conditions, but those exceptions are caught per case and the CLI returns 0 with a partial report. Choose/document consistent task-compliant fatal-manifest vs per-case execution semantics and test actual exit codes. Correct the implementation report's protection claims to match verified behavior. Remove the committed whitespace errors at docs/evaluation/local-image-evaluation.md lines 3–5 and 17 (git diff HEAD~1 HEAD --check currently fails); check the committed diff as well as the working tree.

## Correction scope

Continue DLK-M3-044; no new task packet or production changes. Resolve R1–R3 within existing allowed tooling/tests/docs, rerun focused tests and sample CLI cases, validate task and whitespace, and record actual outcomes. Include this review in the local correction commit. Do not stage scratch outputs, push, create a PR or merge.
