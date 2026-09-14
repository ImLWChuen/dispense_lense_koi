---
task_id: DLK-M3-014
reviewed_commit: 0e220344f9e96fa40a5443db9f72e9cfa5fb5ce5
decision: changes_requested
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-014

## Decision

Changes requested for the remaining verification gap below. DLK-M3-013 R1 is resolved: request field validation rejects PENDING and IN_PROGRESS before route execution; the route also guards these states. No further production-code correction is requested by this review.

## Acceptance evidence

- Inspected the complete correction diff, task report, prior review, session factory, and production rollback boundaries at the exact commit above. Working tree was clean before review.
- Both rollback scenarios now use the real append operation and a before_commit hook; the repository case exercises the self-managed transaction. Independent sessions check that newly appended rows are absent. No manual test rollback is used as the mechanism under test.
- The schema correction is endpoint-specific. Diagnostic semantics, migrations, and database schema are unchanged. Audit acknowledgements and provenance spelling were corrected.
- Gemini reports 22 check API tests, 28 persistence tests, and 208 total backend tests passing. These results are implementer-reported; database tests were not rerun during this review. Reviewer task validation returned VALID and committed-diff whitespace inspection passed.

## Findings

### R1 — P2: Make rollback proof assertions observable outside the handled request

In backend/tests/integration/test_check_result_api.py, fail_after_flush_before_commit sets hook_called=True before asserting the pending rows. If a subsequent assertion fails, the endpoint catches AssertionError in its generic exception handler and returns the same sanitized 500 that this test expects. hook_called remains true, the synthetic path is absent, and the post-request assertions can all pass. The test therefore does not reliably prove that all required pending rows were observed before the deliberate fault.

Capture immutable evidence about pending rows in the hook and assert it after client.post returns. Set a separate fault_reached marker immediately before raising the intended RuntimeError and assert it outside the request. Do not rely solely on assertions that the route can swallow. Preserve the real write/flush path and independent-session rollback verification.

The API and repository rollback tests, and the unfinished-state API regression, also claim prior snapshots/control state are unchanged while comparing only counts, revision numbers, and empty check lists. Capture complete relevant case fields, observation contents, answer/check histories, and revision result_snapshot values before the request, then compare them after the failure/rejection from an independent session. Compare the control case's full baseline too. Existing rows can be modified without changing their counts or revision numbers; the task explicitly requires unchanged prior snapshots and histories.

## Follow-up

Planner should carry this bounded test correction into the next correction packet. No new task was generated. Retain DLK-M3-013 and DLK-M3-014 as unaccepted until the evidence gap is closed. Review/queue edits remain uncommitted; no push or merge was performed.
