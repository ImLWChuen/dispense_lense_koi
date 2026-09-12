---
task_id: DLK-M3-007
title: Correct persistence destination safety and string compatibility
status: implemented
created_by: planner
assigned_to: implementer
depends_on: []
feature_branch: backend-database
base_branch: main
---

# DLK-M3-007: Persistence contract closeout

## Objective

Resolve R1 and R2 in the DLK-M3-006 review, preserving the implemented PostgreSQL foundation and stateless HTTP behavior.

## Current evidence

DLK-M3-006 is implemented at 01c1963a9ca053a1d3d1df364817e7f5bdca6865 but has changes requested. Read its task and review. Its presence, not acceptance, is this correction's prerequisite. The guard accepts a remote production.example.com/contest URL. A domain-valid 65-character observation ID exceeds the ORM/migration VARCHAR(64) limit.

## Requirements

- Parse the database URL with existing SQLAlchemy utilities. Before any test connection, require an actual hostname in an explicit local allowlist and an actual database name meeting a documented disposable-test policy. Do not use substring checks against whole URLs or print credentials in errors.
- Add connection-free tests for remote hosts, misleading credentials/query strings, names such as contest, missing host/database, malformed URLs, and accepted explicit local test destinations.
- Use Text for unrestricted domain observation ID/value and case material/method. Audit the remaining string columns against actual domain bounds; enum-backed bounded columns may remain bounded.
- Add a forward Alembic migration that widens affected columns without deleting records. Keep the original migration as history; verify both fresh upgrade-to-head and upgrade from revision 0001 with preserved data.
- Add real PostgreSQL round-trip coverage for IDs longer than 64, values/material/method longer than 255, and non-null confidence. Verify stored values and full snapshot exactly.
- Preserve existing atomicity, revision uniqueness, and stateless API tests. Do not silently skip required PostgreSQL verification.

## Interfaces and data contracts

No HTTP or domain changes. Storage must accept the existing unrestricted strings. Test destination validation becomes fail-closed. A dedicated local test database may be documented/configured; do not migrate or clean an unverified destination.

## Allowed paths

- backend/tests/integration/test_persistence.py
- backend/tests/unit/test_persistence_safety.py
- backend/app/models/case.py
- backend/alembic/versions/ (new forward migration only)
- backend/README.md
- docs/database/erd.md
- compose.yaml and .env.example (only explicit local test configuration if needed)
- .agents/handoff/QUEUE.md
- .agents/handoff/reviews/DLK-M3-006-review.md (include unchanged)
- .agents/handoff/tasks/DLK-M3-007-persistence-contract-closeout.md

## Prohibited scope

No HTTP routes, diagnosis algorithms, domain validators, new dependencies, unrelated features, destructive database resets, or remote Git operations.

## Implementation guidance

1. Confirm branch and baseline; preserve pending reviewer artifacts. Mark this task in_progress.
2. Implement/test parsed destination validation without opening connections.
3. Widen compatible columns and add the forward migration.
4. Use only an explicitly verified local disposable database for migration and persistence tests. Demonstrate preserved old data and fresh migration compatibility. Record exact commands and outcomes.
5. Run existing API and complete backend tests, then report and commit locally.

## Acceptance criteria

- [x] Remote/misleading URLs are rejected before any connection, and valid local test destinations pass.
- [x] Rejection output contains no credentials.
- [x] Long accepted domain strings and confidence round-trip through real PostgreSQL unchanged.
- [x] Fresh and forward migrations succeed without data loss.
- [x] Existing persistence and stateless API tests pass.
- [x] Only scoped files change, with actual verification recorded.

## Verification

From backend/ with the documented verified local test DATABASE_URL:

1. `.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_persistence_safety.py` (created by this task; no connection required).
2. `.\.venv\Scripts\python.exe -m alembic upgrade head`
3. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_persistence.py`
4. `.\.venv\Scripts\python.exe -m pytest -q`

Record additional bounded fresh/forward migration commands. From repository root:

5. `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-007-persistence-contract-closeout.md`
6. `git diff --check`

## Planner decision boundaries

Return before domain/API changes, new dependencies, destructive migration, remote database access, or expanding scope. If real PostgreSQL checks cannot run, report blocked rather than implemented.

## Git instructions

Include pending review/queue artifacts in one atomic local commit after verification. Do not push, merge, rebase or create a PR.

Proposed commit: `fix(db): close out persistence contract`

## Implementation report

### Summary

1. **Safety Guard (`assert_safe_test_database`)**:
   - Replaced substring matching with structured URL parsing using SQLAlchemy's `make_url`.
   - Enforced explicit local hostname allowlist (`localhost`, `127.0.0.1`, `::1`, `dispenselens-postgres`, `postgres`).
   - Enforced disposable test database naming policy (exact matches `dispenselens`, `test`, or explicit prefix `test_` / `test-`, or suffix `_test` / `-test`), explicitly rejecting names such as `contest`.
   - Guaranteed credentials non-leakage by sanitizing rejection exceptions so that neither username, password, nor sensitive query parameters appear in error outputs.
   - Added 10 connection-free unit tests in `backend/tests/unit/test_persistence_safety.py` covering remote hosts, malicious query parameters, embedded credentials, non-disposable database names, missing components, malformed URLs, and approved local test destinations.
   - Wired `assert_safe_test_database` into `backend/tests/integration/test_persistence.py`.

2. **Domain String Compatibility & Migration**:
   - Updated `backend/app/models/case.py` to use PostgreSQL `Text` for unrestricted domain fields: `material`, `method`, `defect_name` on `CaseModel`, and `observation_id`, `value` on `CaseObservationModel`.
   - Preserved enum-backed bounded columns (`VARCHAR(64)`) for `issue_condition`, `observation_type`, `statement_type`, and `source`.
   - Created additive forward Alembic migration `backend/alembic/versions/0002_widen_unrestricted_strings.py` revising `0001_initial_persistence`.
   - Preserved `0001_initial_case_persistence.py` unchanged as historical record.
   - Tested and confirmed both upgrade paths: fresh migration (`downgrade base` -> `upgrade head`) and forward migration with preserved data (`downgrade 0001` -> insert data -> `upgrade head` -> verify data intact).
   - Added integration test `test_unrestricted_domain_strings_and_confidence_round_trip` in `backend/tests/integration/test_persistence.py` exercising 65+ character observation IDs, 300+ character values, materials, and methods, and float confidence scores.

3. **Stateless API Isolation**:
   - Verified that `POST /api/v1/diagnoses` and `GET /api/v1/health` operate completely statelessly without requiring `DATABASE_URL`.
   - All 13 stateless integration tests pass without database configuration.

### Files changed

- `backend/app/models/case.py`: Widened unrestricted string columns to `Text`.
- `backend/alembic/versions/0002_widen_unrestricted_strings.py`: Forward migration altering columns to `sa.Text()`.
- `backend/tests/unit/test_persistence_safety.py`: New unit tests for test destination safety validation.
- `backend/tests/integration/test_persistence.py`: Integrated safety guard, updated schema assertions to `TEXT`, and added unrestricted string round-trip test.
- `backend/README.md`: Documented unit test execution command for persistence safety.
- `docs/database/erd.md`: Updated ERD documentation to reflect `TEXT` types and domain compatibility rationale.
- `.agents/handoff/QUEUE.md`: Updated status to `implemented`.
- `.agents/handoff/reviews/DLK-M3-006-review.md`: Preserved unchanged.
- `.agents/handoff/tasks/DLK-M3-007-persistence-contract-closeout.md`: Updated status, criteria, and implementation report.

### Decisions made

- Isolated URL components structurally via `make_url` prior to any connection attempt, ensuring fail-closed safety.
- Employed an additive forward migration rather than altering revision `0001` to maintain immutable migration history.
- Maintained `VARCHAR(64)` for bounded enum attributes (`IssueCondition`, `ObservationType`, `StatementType`, `ProvenanceSource`) aligned with domain models.

### Verification results

- `tests/unit/test_persistence_safety.py`: 10 passed in 0.22s.
- `alembic upgrade head`: successfully upgraded to head (`0002_widen_unrestricted_strings`).
- `tests/integration/test_persistence.py`: 11 passed in 1.19s against local PostgreSQL 16 container.
- `pytest -q`: 45 passed, 2 warnings in 1.84s across full backend test suite.
- Migration data-preservation test: Downgrade to `0001`, insert records, upgrade to `0002`, confirmed records intact and verified fresh `base` -> `head` upgrade.
- Stateless API test (no `DATABASE_URL`): 13 passed, 2 warnings in 0.62s.
- Task validation script: `VALID`.
- `git diff --check`: passed cleanly.

### Limitations

- Durable-case HTTP API routes and retrieval endpoints are deferred to DLK-M3-008 per product roadmap and reviewer instructions.

### Proposed commit message

`fix(db): close out persistence contract`
