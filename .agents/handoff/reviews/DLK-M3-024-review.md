---
task_id: DLK-M3-024
reviewed_commit: 2f60f9292b07edfe6982996e1d10cdfe84d48d66
decision: accepted
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-024

## Integration follow-up

Gemini correction `6bac591dac9098fdf2c6bfc4e93a01cb492439d1` is accepted by static review: the regression retains equality of stable case/diagnosis fields and explicitly checks GET's revision-1 history against the initial persisted diagnosis. Production code is unchanged. Gemini reports 312 backend tests passed before subsequent integration.

The pending user-authorized publish/merge encountered newer remote main `5293817` (PR #11, AI diagnosis engine integration). It was merged locally at `5b5f89c79d1a0d7572240c100a0480aa89dc3a90`. The reviewer ran the combined backend suite: pytest stopped with 16 collection errors, including missing `CaseCauseConfirmationModel` and `CaseOutcomeSummary`. The incoming changes also remove the previously accepted cause-confirmation, recovery, recurrence, and report routes from cases.py. This is a new integration regression, not a rejection of Gemini's test correction or the earlier scoped acceptance.

Publishing is blocked pending reconciliation of the incoming model/repository/schema/route and migration changes with accepted Member 3 contracts. Preserve both sides' useful work; do not silence missing imports, drop accepted tests, or delete durable data to make the suite pass. Compare against pre-integration commit `6bac591`, restore compatible lifecycle/report persistence and endpoints while retaining new teammate features, inspect migration continuity without rewriting applied migrations, then verify the full backend suite. Production reconciliation remains Gemini's implementation work under PROJECT.md. No remote push or merge was performed in this review; local main was not advanced. No new task packet was generated.

### Integration resolution

Reconciled local integration commit `5b5f89c` with baseline `6bac591`:
- Restored Member 3 persistence models (`CaseCheckResultModel`, `CaseCauseConfirmationModel`, `CaseLifecycleEventModel`) and relationships alongside teammate's `CheckExecutionModel`.
- Restored Member 3 schemas (`CaseOutcomeSummary`, `CaseReportResponse`, `SubmitCheckResultRequest`, `CaseCheckResultResponse`, `CaseRecoveryActionResponse`, `CaseRecoveryVerificationResponse`, `CaseRecurrenceResponse`, `CauseConfirmationRecord`, `LifecycleEventRecord`, `CheckResultRecord`, `QuestionAnswerRecord`) alongside teammate's schemas.
- Preserved migration continuity by chaining teammate's check execution table migration as `0007_check_execution_history` (revising `0006_lifecycle_event_history`) without rewriting applied migrations `0001` through `0006`.
- Restored repository methods and snapshot hydration for all lifecycle stages; synchronized check execution and check result persistence.
- Restored all lifecycle routes (`POST /{case_id}/check-results`, `/cause-confirmations`, `/recovery-actions`, `/recovery-verifications`, `/recurrences`, `GET /{case_id}/report`, `GET /{case_id}/report.pdf`) alongside teammate's `POST /{case_id}/checks`.
- Full backend suite verified: 343 passed, 0 failed.

## Acceptance review

Accepted at correction commit `2f60f9292b07edfe6982996e1d10cdfe84d48d66`. This decision supersedes the historical findings below. No blocking findings remain for the scoped backend acceptance milestone.

- R1 resolved: the empty-list test binds the real repository to a dedicated PostgreSQL connection and uncommitted transaction, removes rows only within that transaction, asserts an exact empty array, and rolls back in finally. The dependency override is removed during cleanup. No permanent deletion is performed by this test.
- R2 resolved: the failing list request now compares complete tracked-case state using independent sessions and asserts the exact sanitized response. The combined read test asserts every setup mutation and verifies revision 7 / RECURRED, seven revisions, and populated histories before capturing its baseline. Failure injection remains at get_all_cases; the previously suggested later injection point was a preference, not an unmet requirement.
- R3 resolved: the handoff documents HTTP 422 for extra finding_text, the 64-character actor limits, and the actual verifyCase method and response-wrapper mismatch. Member 1 owns the corresponding frontend corrections.
- Reviewed the correction diff and session/dependency plumbing; no production code, schema, dependency, frontend, or diagnostic-semantic changes were introduced by this correction.
- Reviewer verification: committed whitespace check passed and task validator returned VALID. Gemini reports 15 focused acceptance tests passed in 5.02s and 312 backend tests passed with zero failures/skips in 48.07s. PostgreSQL tests were not rerun by the reviewer under the project role split.

The scoped Member 3 competition-MVP backend milestone is accepted. This is not acceptance of the full integrated frontend application: documented Member 1 wiring/type/request corrections and final team demonstration remain separate work. Optional deferred features remain deferred. No next task, commit, push, or merge was performed by the reviewer.

## Original review (historical)

## Decision

Changes requested. The lifecycle walkthrough, cross-event stale-write snapshots, six-defect API coverage, and list error sanitization are present. The final acceptance evidence and Member 1 contract handoff need the bounded corrections below before declaring the backend milestone complete.

## Findings

### R1 - P2: Actually verify the empty-list result

`backend/tests/integration/test_mvp_backend_acceptance.py:155-164` neither establishes an empty database nor asserts `resp.json() == []`. It only asserts HTTP 200 and that the response is a list, so it passes against any populated database and would accept a fabricated nonempty response. The task explicitly requires real PostgreSQL empty-result verification, and the report currently claims this is proved.

Use an isolated PostgreSQL database/schema or a safely isolated transaction/dependency setup that makes the real repository see no cases. Assert the empty response exactly. Do not delete unrelated development cases or substitute a mocked empty repository for the required integration proof. Document the isolation and cleanup mechanism.

### R2 - P2: Complete the required failure-path and rich-state nonmutation proofs

`backend/tests/integration/test_mvp_backend_acceptance.py:240-252` verifies sanitization only: it captures no durable state before/after the failing list request. Task 2 explicitly requires the internal read-failure scenario to be non-mutating. Use a tracked persisted case and independent-session complete-state snapshots around the injected failure; retain the sensitive-marker check. Prefer injecting a read failure after cases have been retrieved so the route's assembly failure path is exercised.

In `test_all_public_read_surfaces_read_only_proof` at lines 527 onward, every setup mutation response is discarded. If setup starts failing, this proof can silently run against an initial or partially populated case. Assert each setup response and expected revision, then assert the baseline reached revision 7 / RECURRED with all four histories populated before taking snapshots. Reuse an asserted workflow helper if convenient. Keep the existing full snapshot comparison across all read requests.

### R3 - P2: Correct the contract handed to Member 1

`docs/api/frontend-backend-contract.md:29` says the backend ignores extra check-result fields. `SubmitCheckResultRequest` uses `extra="forbid"`; when the frontend sends a defined `finding_text`, that request is rejected with HTTP 422. Record this as a request incompatibility and instruct Member 1 to remove/map the field to accepted `outcome`/`finding_details` as appropriate. Do not weaken the backend schema.

The actor limits at lines 61-66 are 64 characters, not 100, as the committed schema and new OpenAPI test already show. Correct the matrix and stale test comments. Align the task report with the actual frontend names/types: `casesApi.verifyCase` exists and is typed `Promise<DiagnosisResult>`; the report's `verifyResolution` and described response shape do not match the source. A frontend helper name differing from a backend operation name is not itself a contract mismatch. Preserve the real response-wrapper mismatch and leave frontend implementation to Member 1.

## Acceptance evidence and limitations

- Reviewed the exact local commit and its production, test, and documentation changes on `backend-database`; working tree was clean before this review.
- The list route now returns a sanitized 500 for unexpected assembly/repository errors. The public lifecycle test checks revisions 1-7, retained histories, cause confirmation independent of issue condition, and JSON/PDF report basis.
- The added six-defect parametrization exercises stateless evaluation and durable creation without editing Member 2 knowledge or engine code.
- Creation-time defect-name fallback is a small additional production change outside the packet's explicitly listed list/read correction paths. It uses existing knowledge labels and leaves response shape unchanged; no functional defect was identified in it. Future implementation reports should explicitly identify such scope deviations and their regression evidence before claiming exact scope compliance.
- Reviewer checked the committed diff for whitespace errors (passed) and ran task validation (VALID).
- Gemini reports 15 new acceptance tests and 312 full backend tests passing with no failures/skips. The reviewer did not rerun PostgreSQL suites under the planner/implementer role split. Passing counts do not resolve the missing assertions above.

## Follow-up

Give R1-R3 to Gemini as corrections within DLK-M3-024, and update the task report to reflect actual verified behavior. No new task packet was generated. The backend completion declaration remains pending this review. Only the review and queue were edited; no production changes, commits, pushes, or merges were performed.
