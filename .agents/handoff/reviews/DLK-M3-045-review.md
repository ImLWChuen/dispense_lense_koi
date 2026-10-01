---
task_id: DLK-M3-045
reviewed_commit: ce34c7db0b91141be69279df60cb4be35966473a
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-045

## Decision

Follow-up at ce34c7db0b91141be69279df60cb4be35966473a: changes requested for one remaining R3 metric-integrity gap. R1 failure classification is resolved; R2 remains resolved. Exact ROI membership, malformed-report handling and count consistency checks address the previous structural findings. Gemini reports 66 focused tests passing; reviewer inspected the implementation and tests without rerunning them under the planner/executor separation. Committed whitespace check passes.

### R3 remaining — P2: Derive or validate the percentages actually rendered

In backend/tests/inspection_robustness_summary.py:232–263, validate_identities compares status_accuracy, abstention_rate and false_missing_rate numerators/denominators with compute_dataset_metrics, but never checks their rate fields. generate_markdown_summary at lines 406–427 still formats rates from the original report. Consequently changing only status_accuracy.rate to 0.25 while retaining matching 6/6 counts passes these checks and renders 25.0% (6/6). The same gap affects abstention and false-missing rates; out-of-range or nonfinite numeric values can also become misleading displayed percentages. The contradictory-summary regression changes successful_cases only and does not cover this path. This finding follows from source inspection, not an independently executed reproduction.

Use canonical recomputed metrics for every displayed count/percentage, or validate all consumed rates as finite numeric non-boolean values consistent with recomputed metrics and the evaluator's zero-denominator semantics. Do not silently default a missing rate to zero. Add CLI regression cases changing only each of these three rate fields, including missing, string, boolean, out-of-range and nonfinite values. Require either safe rejection (nonzero exit, no traceback/private marker, no output publication) or a clearly consistent policy of rendering canonical recomputed values; valid evaluator reports must remain supported. Continue DLK-M3-045 only, rerun its focused checks and update its implementation report. No production changes or new task packet.

Completion remains manual-region prototype 90–95%, full roadmap 65–75%; these are scope estimates, not measured real-image accuracy. Review and queue edits remain uncommitted for Gemini's next local commit. No remote Git operations performed.

## Historical first follow-up

Follow-up at 055e48b3c34dd085a67c63a96715b26255b1b348: R2 is resolved with corrected runtime/measurement values, qualified conclusions and recorded fixture inspection. Hardcoded scenario narratives were removed and safe publication is reused. Gemini reports 57 focused tests passing; reviewer inspected code/evidence without rerunning tests. Committed whitespace check passes. Two bounded R1/R3 gaps remain.

### R1 remaining — P2: Do not classify every execution error as an inspection defect

classify_case_finding still maps every ERROR to DEMONSTRATED_DEFECT. A missing file, permission failure or deliberately corrupt image therefore becomes a claimed demonstrated algorithm defect, despite the prior explicit requirement to distinguish execution failures from demonstrated inspection failures. Add a separate execution/input-failure category and inventory with the recorded error category; reserve control mismatch claims for actual supplied labels versus predictions. Test FILESYSTEM_ACCESS and IMAGE_VALIDATION errors separately from a wrong labeled prediction. Do not call incomplete/missing status_match agreement; compute agreement from validated expected/predicted states or reject inconsistent records.

### R3 remaining — P2: Validate complete site records and reject malformed reports cleanly

validate_identities iterates only sites that happen to exist in the report. Deleting one labeled site's record, or setting sites=[], passes validation; summary metrics can still say 100% and complete coverage from the unchanged report summary. Duplicate/unknown site IDs are not rejected. Further, current_image_path=123 causes .strip() AttributeError, sites=null/non-object entries cause iteration/.get errors, and malformed numeric summary fields can crash generate_markdown_summary. main catches only IdentityMismatchError and leaves these exceptions as tracebacks.

Validate one site record per configured ROI (missing predictions must be represented explicitly with output_present=false, as the evaluator already does), unique/exact ROI membership, structural types and label/status consistency. Recompute metrics using the accepted compute_dataset_metrics helper or reject summary discrepancies so a stale success total cannot contradict records. Validate numeric metric structures before formatting. Return fixed, safe CLI errors for malformed reports; do not echo raw report paths/values from identity exceptions. Add CLI tests for removed/duplicate/unknown sites, sites=null, non-object site, non-string image path and contradictory summary; require nonzero exit, no traceback/private marker and no output file. Keep valid evaluator outputs working.

Continue DLK-M3-045 only; no production changes or new task packet. Rerun focused checks and update the report. Completion remains manual prototype 90–95%, full roadmap 65–75%; no accuracy claim.

## Historical initial findings

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
