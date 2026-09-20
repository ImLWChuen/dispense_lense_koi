---
task_id: DLK-M3-009
reviewed_commit: 468ee3d311db7bcea114f580e28539602a91967b
decision: changes_requested
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-009

## Decision

Changes requested for the required atomic-failure verification. The inspected create/retrieve implementation otherwise provides the intended initial durable workflow. No production rollback defect is claimed by this review.

## Acceptance evidence

- Reviewed exact commit 468ee3d311db7bcea114f580e28539602a91967b on backend-database; working tree was clean, six commits ahead of the locally tracked remote. Changes are in scoped paths.
- POST prepares a StructuredCase, invokes the real engine, flushes through the existing repository and commits the shared dependency session. Exception paths roll back. GET reads case, observations and revision 1 from PostgreSQL, with no engine invocation or write.
- Existing stateless route/schema, database models, migrations and diagnostic engine are unchanged. Tests exercise create/retrieve, client observations, long strings, unknown IDs, repeated GET and no recalculation.
- Gemini reports 13 case API tests and 65 total backend tests passing, plus database-free stateless/OpenAPI checks. These are implementer-reported results; no application tests were rerun in this review, consistent with the project role split.
- The committed task has one extra blank line at EOF. This is nonblocking. Its report also names migration 0002_widen_domain_strings, whereas the existing revision is 0002_widen_unrestricted_strings, and describes a context-manager transaction implementation different from the actual dependency/session code.

## Findings

### R1 - P2: Exercise rollback after actual writes

backend/tests/integration/test_case_api.py:379 replaces save_initial_case entirely with an immediate RuntimeError. No case, observation or revision is ever inserted, so finding no case afterwards does not demonstrate the required rollback of partial writes. The generated failing_case_id is unused, and the final query checks only cases by description. This test would also pass if the route stopped rolling back a partially completed transaction.

Add a real PostgreSQL API failure scenario that executes real repository writes/flushes, proves those writes occurred in the request transaction, then injects a failure before commit. Capture the actual case ID and verify from a fresh independent session that all three tables contain no records for it. Preserve and verify unrelated pre-existing data. Retain the existing immediate-error test if useful, but do not describe it as proof of partial-write rollback.

## Contract limitation

backend/app/api/cases.py:64 rejects an engine result without an analysis revision with HTTP 422. This occurs when evidence cannot identify a defect, even though the stateless endpoint accepts that input and returns an inconclusive result. The accepted repository requires revision 1, so changing this behavior needs an explicit contract decision; do not fabricate a revision or change engine semantics as part of the test correction. Document and test the current limitation and return any requested durable-inconclusive-case support to the planner. This review does not approve that limitation as the final product behavior.

## Follow-up

DLK-M3-010 supplies the bounded verification/documentation correction. Keep later workflows unreleased. No implementation fixes, test runs, commits or remote Git operations were performed during review. Review/queue/task artifacts remain local and uncommitted for Gemini.
