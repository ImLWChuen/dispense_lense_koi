---
task_id: DLK-M3-008
title: Close PostgreSQL effective-destination safety bypass
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-007]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-008: Effective test-destination safety closeout

## Objective

Close the remaining PostgreSQL test safety bypass so a URL cannot pass as local and then redirect the actual connection through query parameters. Preserve the accepted schema widening, migration, persistence behavior, and stateless HTTP behavior from DLK-M3-007.

## Current evidence

DLK-M3-007 is implemented at `5114c50eb75712622c5f6f8497146f325b11ab11` with changes requested in `reviews/DLK-M3-007-review.md`. Reviewer replay confirmed 11 PostgreSQL persistence tests and all 45 backend tests pass. However, `assert_safe_test_database` accepts `postgresql+psycopg://user:pass@localhost:5432/test_db?host=production.example.com`; SQLAlchemy/Psycopg resolves the effective host to `production.example.com`. It also accepts a remote `hostaddr` query parameter. The current adversarial test covers a remote authority pretending to be local, but not a local authority redirected by its query string.

## Requirements

- Before any connection, ensure every accepted URL has an effective database destination that remains within the existing explicit local-host and disposable-database policy.
- Fail closed on PostgreSQL query parameters that can replace or redirect connection host, address, database, service, or other destination fields. A simple policy rejecting all query parameters is acceptable if documented and compatible with the repository's test URL.
- Add connection-free inverse adversarial tests for a local URL authority combined with at least query-level `host`, `hostaddr`, `dbname`, and `service` redirection. Cover any additional destination-redirection mechanism that the chosen implementation explicitly permits.
- Preserve credential-free and secret-free rejection messages. Existing approved query-free local URLs must continue to pass.
- Preserve all schema, migration, persistence, API, and domain behavior.

## Interfaces and data contracts

No product, HTTP, domain, ORM, or migration contract changes. This task changes only the pre-connection test-destination validation policy and its documentation/tests. The guard must reject unsafe input before engine creation or database I/O.

## Allowed paths

- `backend/tests/unit/test_persistence_safety.py`
- `backend/tests/integration/test_persistence.py` only if needed to consume a relocated private test helper
- `backend/README.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-007-review.md` (include unchanged)
- `.agents/handoff/tasks/DLK-M3-008-effective-test-destination-safety.md`

## Prohibited scope

- No ORM, Alembic, repository, HTTP route, diagnosis algorithm, domain model, dependency, or Docker configuration changes.
- No database reset, downgrade, data deletion outside existing isolated test cleanup, or remote database access.
- No push, merge, rebase, pull request, or base-branch change.

## Implementation guidance

1. Confirm the branch and clean baseline, preserve the reviewer artifacts, and mark DLK-M3-008 `in_progress`.
2. Choose one fail-closed rule for PostgreSQL query parameters. Prefer a small explicit policy that a reviewer can reason about without opening a connection.
3. Add inverse adversarial tests that reproduce the reviewed bypass. Tests must remain connection-free and must prove validation occurs before any engine or connection is used.
4. Run the safety tests first, then the real local PostgreSQL persistence suite and complete backend suite. Stop and report `blocked` if the required local PostgreSQL verification cannot run.
5. Inspect the final diff, complete the implementation report, update the queue to `implemented`, and create one atomic local commit.

## Acceptance criteria

- [x] A URL with an approved local authority plus `?host=production.example.com` is rejected before connection.
- [x] A URL with an approved local authority plus a remote `hostaddr` is rejected before connection.
- [x] A URL with an approved local authority plus query-level `dbname` redirection is rejected before connection.
- [x] A URL with an approved local authority plus query-level `service` redirection is rejected before connection.
- [x] Query-level database/service redirection cannot bypass the disposable local test policy.
- [x] Existing approved query-free local test URLs pass, and rejection output exposes no credentials.
- [x] All persistence tests and the complete backend suite pass against verified local PostgreSQL.
- [x] Only scoped files change; no remote Git operation occurs.

## Verification

From `backend/`:

1. `.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_persistence_safety.py`
2. With the documented verified local test `DATABASE_URL`, `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_persistence.py`
3. With the same local test `DATABASE_URL`, `.\.venv\Scripts\python.exe -m pytest -q`

From repository root:

4. `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-008-effective-test-destination-safety.md`
5. `git diff --check`

## Planner decision boundaries

Return to the planner before changing product interfaces, database schema, migrations, dependencies, Docker configuration, or the existing local/disposable naming policy. Do not weaken validation to make an adversarial test pass.

## Git instructions

Create one atomic local commit after all required checks pass. Include the unchanged DLK-M3-007 review and this ready task. Do not push, merge, rebase a shared branch, create a pull request, or change the base branch.

Proposed commit message: `fix(test): validate effective database destination`

## Implementation report

### Summary

- Closed the connection-redirection safety bypass in `assert_safe_test_database` in `backend/tests/unit/test_persistence_safety.py`.
- Defined `FORBIDDEN_DESTINATION_QUERY_KEYS` (`host`, `hostaddr`, `port`, `dbname`, `database`, `service`, `servicefile`, `passfile`, `target_session_attrs`).
- Updated `assert_safe_test_database` to fail closed before any connection if query parameters attempt to redirect or override host, address, database, or service parameters, and to reject all query parameters on test database URLs.
- Sanitized all exception outputs so that neither credentials (username/password) nor query parameters leak into error messages.
- Added 7 inverse adversarial unit tests in `backend/tests/unit/test_persistence_safety.py` covering:
  - Local authority with query-level `?host=` redirection (e.g. `production.example.com`, `remote.database.net`, and query-level `localhost`);
  - Local authority with remote `?hostaddr=` redirection (e.g. `203.0.113.10`, `198.51.100.25`);
  - Local authority with query-level `?dbname=` / `?database=` redirection (preventing policy bypass via query string);
  - Local authority with query-level `?service=` and `?servicefile=` redirection;
  - Query-level `?port=` and `?target_session_attrs=` overrides;
  - General query parameter fail-closed enforcement;
  - Credential non-leakage on adversarial query redirection URLs.
- Documented the test safety policy and query parameter prohibition in `backend/README.md`.
- Preserved all schema widening, migrations, persistence behavior, domain models, and stateless API contracts from DLK-M3-007.

### Files changed

- `backend/tests/unit/test_persistence_safety.py`: Implemented query parameter destination checks and 7 inverse adversarial unit tests.
- `backend/README.md`: Documented test destination safety policy and query parameter prohibition.
- `.agents/handoff/QUEUE.md`: Updated active task status to `implemented`.
- `.agents/handoff/reviews/DLK-M3-007-review.md`: Included unchanged.
- `.agents/handoff/tasks/DLK-M3-008-effective-test-destination-safety.md`: Updated status, criteria, and implementation report.

### Decisions made

- Explicitly checked `FORBIDDEN_DESTINATION_QUERY_KEYS` to provide exact, diagnostic rejection errors when destination-redirecting parameters are supplied, while also rejecting all query parameters on test connection strings to guarantee a fail-closed policy.
- Maintained credential sanitization across all failure modes so that passwords and usernames embedded in test URLs are strictly withheld from exception messages.

### Verification results

- `tests/unit/test_persistence_safety.py`: 17 passed in 0.23s.
- `alembic upgrade head`: success (revisions intact at `0002_widen_unrestricted_strings`).
- `tests/integration/test_persistence.py`: 11 passed in 1.24s against local PostgreSQL 16 container.
- `pytest -q`: 52 passed, 2 warnings in 1.84s across full backend test suite.
- Stateless API tests without `DATABASE_URL`: 13 passed in 0.58s.
- Task validation script: `VALID`.
- `git diff --check`: clean (no whitespace or conflict errors).

### Limitations and follow-up

- Durable-case HTTP API endpoints remain deferred pending review and acceptance of this safety closeout.

### Proposed commit message

`fix(test): validate effective database destination`

