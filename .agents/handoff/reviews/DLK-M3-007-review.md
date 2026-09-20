---
task_id: DLK-M3-007
reviewed_commit: 5114c50eb75712622c5f6f8497146f325b11ab11
decision: changes_requested
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-007

## Decision

Changes requested. The schema compatibility correction and forward migration meet their intended contract, and all backend tests pass against local PostgreSQL. One connection-redirection path still bypasses the destination safety guard, so the persistence work cannot yet be accepted.

## Acceptance evidence

- Commit `5114c50eb75712622c5f6f8497146f325b11ab11` stays within the task's allowed paths. The working tree was clean on `backend-database`, four commits ahead of the locally tracked remote reference. No remote operation was performed.
- `CaseModel.material`, `CaseModel.method`, `CaseModel.defect_name`, `ObservationModel.observation_id`, and `ObservationModel.value` now use `Text`. Revision `0002_widen_unrestricted_strings` widens the existing columns without replacing revision `0001`.
- The real PostgreSQL round-trip test covers observation IDs longer than 64 characters, material/method/value strings longer than 255 characters, and non-null confidence. The schema inspection asserts the widened column types.
- Reviewer replay against the repository's local PostgreSQL 16 container: `alembic upgrade head` succeeded; `tests/integration/test_persistence.py` passed 11 tests; the complete backend suite passed 45 tests with two dependency deprecation warnings. The container was stopped after verification.
- Connection-free safety tests passed 10 tests, stateless diagnosis/health tests passed 13 tests, the task validator reported `VALID`, and `git diff --check HEAD^ HEAD` was clean.

## Findings

### R1 - P1: Validate or reject PostgreSQL query parameters that override the destination

`backend/tests/unit/test_persistence_safety.py:61` validates only `parsed.host`, and the database check similarly uses the URL path. PostgreSQL connection query parameters can replace those fields after this guard succeeds. A connection-free reviewer reproduction passed `postgresql+psycopg://user:pass@localhost:5432/test_db?host=production.example.com` through `assert_safe_test_database`; SQLAlchemy/Psycopg then produced effective connection arguments with host `production.example.com`. The same guard also accepted `?hostaddr=203.0.113.10` and a query-level port override.

This leaves the destructive test fixture able to connect and clean a non-local database even though the visible URL authority is allowlisted. Fail closed on destination-altering query parameters, or validate the effective connection arguments rather than only the top-level URL components. Add inverse adversarial tests in which the URL authority is local but the query string redirects the connection. Keep rejection messages credential-free.

## Follow-up

DLK-M3-008 is the bounded correction packet. The string widening, migration, and persistence round-trip work do not require redesign. Durable diagnosed-case HTTP work remains gated on acceptance of this safety closeout. Remote Git operations remain unauthorized unless the user explicitly changes that instruction.
