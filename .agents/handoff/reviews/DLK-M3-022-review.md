---
task_id: DLK-M3-022
reviewed_commit: e68015c4587b5f5afe7b14e78b2fe161dd3bf40c
decision: accepted
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-022

## Decision

Accepted after correction commit e68015c4587b5f5afe7b14e78b2fe161dd3bf40c. The original findings below are retained as review history and superseded by this closeout.

## Correction review

- R1 resolved: the assembler selects an immutable revision, reads issue condition and defect basis from that revision, and scopes all four histories with max_revision. The integration test commits a valid R7 recurrence through an independent writer session after the report has selected R6; it asserts a coherent R6 report and confirms the database has advanced to R7. A unit test separately checks pinned state against a differing mutable case condition.
- R2 resolved: the sanitized-error test now uses a rich case, injects failure in get_case_check_results after earlier report reads, and compares complete state snapshots from independent sessions before and after the failed GET.
- R3 verification counts corrected: implementer reports recurrence 9, recovery verification 23, cause confirmation 17, report integration 9, report unit 8, and full backend 283 passed with 0 skipped. Reviewer did not rerun database tests. Committed whitespace check passed and task validation returned VALID.
- Remaining nonblocking report-text cleanup: task report still calls the top-level fields current_defect_code/current_issue_condition; actual schema fields are defect_code/issue_condition. Its successful nonmutation test name should be test_report_read_only_state_proof. Carry these documentation corrections into the next authorized task; do not change API fields to match prose.
- No new blocking defect identified in the supported durable workflow. Review and queue edits remain local; no implementation changes, commit, push, or merge performed.

## Findings

### R1 — P2: Assemble the report from one consistent revision basis

In backend/app/services/reporting/report_generator.py:147-207, case state, latest revision, and four unrestricted histories are read separately. The request session has no configured consistent-snapshot isolation or case lock, and history queries omit the supported max_revision bound. Under the normal PostgreSQL READ COMMITTED configuration, a concurrent recurrence commit after the latest-revision read can produce current_revision=6 and a RESOLVED diagnosis alongside the R7 recurrence event. A commit between the case and latest-revision reads can instead leave the top-level condition behind the diagnosis. Such a report misrepresents the audit basis.

Provide a consistent snapshot for the whole report, or use a pinned immutable revision with all histories scoped to that revision and mutable outcome fields derived consistently from that basis. Merely adding max_revision does not fix a case-state/latest-revision mismatch. Add an integration regression that deliberately interleaves a valid writer commit with report reads; assert diagnosis, condition, summary, and histories describe one revision and that report generation itself writes nothing.

### R2 — P2: Complete the required failure-path nonmutation proof

backend/tests/integration/test_case_report_api.py:398 tests the sanitized error by replacing the entire assembler and asserting only status/message. It never captures before/after durable state, although the task Security section explicitly requires zero durable mutation for this failure scenario. Add complete-state snapshots in independent sessions around the failing GET, preferably with a rich case and an assembly/read failure after report reads have begun. Retain the sensitive-marker assertion and compare all case/history/revision data.

### R3 — P2: Correct inconsistent verification evidence and report contract

The task implementation report lists recurrence 19 passed, recovery verification 22 passed, and cause confirmation 19 passed. Those files are unchanged by this commit and contain 9, 23, and 17 unparameterized tests respectively, matching the prior accepted report. The listed per-suite counts cannot be treated as verified evidence for the stated commands. Record actual command output and counts; rerun any command whose output is unavailable. The full-suite 281-pass claim remains implementer-reported, not independently verified by this reviewer.

Also correct the report API description at task line 408 onward: fields such as title, initial_symptoms, dispense_pattern, fluid_type, and updated_at are absent from CaseReportResponse; the actual repository is CaseRepository, not SQLAlchemyCaseRepository. Match history field names to the schema. Do not add invented API fields or change production contracts to fit the report.

## Verification and scope

- Reviewer inspected commit c445855a03ee165db2a05540931c72bb801b014f, source, tests, report, and API additions. Working tree was clean before review artifacts.
- Committed diff whitespace check passed; task validator returned VALID.
- Report unit/integration tests are present (7 and 8 tests). Existing tests cover rich history, empty history, ordering, repeatability, successful-read nonmutation, and no diagnosis recalculation.
- Database suites were not rerun by the reviewer under the project planner/implementer role split. Findings are based on static code and evidence inspection; the concurrency interleaving has not been executed by the reviewer.
- No production corrections, commits, pushes, or merges performed. No new task packet generated.

## Follow-up

R1-R3 correction work is accepted at e68015c4587b5f5afe7b14e78b2fe161dd3bf40c. Future work still requires a separately authorized task; no next task generated during this review.
