---
task_id: DLK-M3-044
reviewed_commit: af41d40dee3a40d82d4eba1a8b3f318d2eba1221
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-044

## Decision

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
