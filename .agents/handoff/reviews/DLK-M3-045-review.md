---
task_id: DLK-M3-045
reviewed_commit: 1f49e9b3bd9ca8629719113c8a24f1d128a11e1f
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-045

## Decision

Changes requested. The deterministic scenario matrix and clean-control/unlabeled separation are useful. Gemini reports 49 focused tests passing. Reviewer inspected code, test coverage and scratch/robustness_checkpoint/report.json without rerunning tests. Committed whitespace check passes. No production changes or remote Git operations performed.

## R1 — P1: Derive summary findings from data rather than fixed conclusions

inspection_robustness_summary.py generate_markdown_summary prints fixed claims such as '100% agreement', 'All cases completed without execution crashes', and a complete hardcoded weakness inventory, regardless of supplied outcomes. classify_case_finding declares every case whose ID contains control consistent with ground truth without checking expected_status/status_match. It also asserts no image-quality warning without inspecting warnings and calls UNRELIABLE gating correct on unlabeled inputs. These statements can contradict the report after a pipeline regression or a different run.

Generate all measured claims from the validated report, use explicit labels/matches for control agreement, preserve execution failures without automatically calling expected invalid-input rejection an algorithm defect, and label unlabeled outcomes as observations requiring review. Do not infer an absent sharpness gate or inevitable production failure from DETECTED alone. Move run-specific human interpretation to the checkpoint document with concrete evidence. Add hand-authored summary tests with a failed case, wrong control, omitted output, warning-bearing detected site, all-unlabeled data and changed blur outcomes; assert no stale success or scenario conclusions survive.

## R2 — P2: Correct the tracked checkpoint using actual evidence

docs/evaluation/inspection-robustness-checkpoint.md runtime versions contradict the local report: report records Python 3.14.0, OpenCV 5.0.0 and Pydantic 2.13.5, not 3.14.0rc2/4.11.0/2.11.0a1. Recorded baseline diameter is 39.94 px and heavy-blur diameter 41.38 px (about +3.6%); the claimed +15–25% expansion is unsupported. Mild blur retains 39.94 px and circularity 0.9526, identical to the control, rather than dropping to approximately 0.94. The 0/4 false-missing figure concerns labeled controls only, not all unlabeled perturbations. Reports include timestamps/timings, so 'exactly identical output reports' is also false.

Reconcile every quantitative statement with report fields and record derived calculations. Separate these measured synthetic outcomes from hypotheses about real cameras; do not prescribe a new focus gate as a proven need without representative validation. Describe deterministic generated inputs and stable non-timing outputs accurately. Record the required representative fixture visual inspection method/artifact paths; no such evidence is in the implementation report. Keep original source commit provenance and identify uncommitted evaluation tooling provenance where relevant.

## R3 — P2: Complete the summary contract and reuse safe publication

The summary omits required per-site warnings, emitted observations/affected IDs, expected/assessed counts and separate reference inspection coverage. It also checks only dataset/case IDs, so a report from different profiles/origin/labels under reused IDs can be presented with the wrong manifest context. Validate the relevant recorded origin/profile/label identity and schema version before summarizing, and render the required fields and failed/missing outputs explicitly. Use UNCALIBRATED for actual features-only analysis status rather than the mode string FEATURES_ONLY.

Summary output currently checks existence and later uses write_text, recreating the no-overwrite race already fixed in DLK-M3-044. Reuse the accepted publish_report_file helper with temporary-file cleanup and existing manifest/report alias guards; do not change the accepted evaluator. Add a sentinel-created-during-generation regression and input-alias checks. Catch malformed report/CLI errors cleanly and avoid raw exception/input leakage by reusing established safe diagnostic patterns.

## Correction scope and progress

Continue DLK-M3-045 within its existing allowed files. No production tuning or new task packet. Rerun focused tests, regenerate summaries from actual evaluator results, update the report and commit locally with this review. No scratch artifacts staged and no push/PR/merge.

Completion estimate remains manual-region prototype 90–95%, broader roadmap 65–75%. This checkpoint is not accepted yet and does not establish real-image accuracy.
