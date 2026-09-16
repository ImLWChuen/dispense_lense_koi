---
task_id: DLK-M3-022
reviewed_commit: c445855a03ee165db2a05540931c72bb801b014f
decision: changes_requested
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-022

## Decision

Changes requested. The persisted report projection, explicit ordering, canonical history mappings, and no-engine design are present. Correct the consistency defect and complete the verification evidence before acceptance.

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

Carry R1-R3 into the next planner-authorized correction work and provide the same feedback to Gemini in chat. Keep dependent report/PDF/frontend work unreleased until this review is resolved.
