---
task_id: DLK-M3-006
reviewed_commit: 01c1963a9ca053a1d3d1df364817e7f5bdca6865
decision: changes_requested
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-006

## Decision

Changes requested. The 23-file commit establishes the intended PostgreSQL foundation and leaves the HTTP application unchanged, but two concrete contract violations require correction before acceptance.

## Acceptance evidence

- Repository validates case/result identity and initial revision, writes case/observations/JSONB snapshot in one session, and rolls back on failure. Revision uniqueness and foreign keys are represented in both ORM and migration.
- Time columns use timezone-aware types. Lazy configuration keeps the stateless HTTP path independent of database startup.
- Reviewer replay: 13 diagnosis/health tests passed with two dependency deprecations and one local pytest-cache warning.
- Gemini reports 10 persistence tests and 34 total tests passing against PostgreSQL. Those database runs were not independently replayed during this review; reviewer verification focused on the two failures below without opening any database connection.
- Working tree was clean at review start on backend-database, three commits ahead of the locally tracked remote reference. No remote refresh or push was performed.

## Findings

### R1 - P1: Parse the test database destination instead of searching the URL

`backend/tests/integration/test_persistence.py`, `_assert_safe_test_database`, searches the entire URL for `postgres` to establish locality. Every supported PostgreSQL URL contains that word in its scheme. It also accepts `test` anywhere, including the name `contest`, credentials, or host. A read-only reproduction passed `postgresql+psycopg://user:password@production.example.com/contest` through the guard successfully. The fixture then uses the supplied connection for committed writes and cleanup. This fails the required local/test destination safety boundary.

Parse the URL, validate the actual hostname against an explicit local allowlist and the actual database name against an explicit disposable-test policy. Fail before connecting on other destinations. Do not echo a credential-bearing URL in rejection messages. Add adversarial guard tests that do not connect to a database.

### R2 - P2: Preserve accepted string lengths in persistence

`backend/app/models/case.py` and `backend/alembic/versions/0001_initial_case_persistence.py` restrict observation IDs to VARCHAR(64), while the accepted domain Observation.id is an unrestricted string. A 65-character ID validates in the domain but exceeds the storage column. Other unrestricted input strings are also narrowed: observation value and case material/method use VARCHAR(255). These valid inputs cannot round-trip through the promised persistence boundary.

Use compatible storage types for unrestricted domain strings in both ORM and Alembic. Do not narrow the public/domain validators to fit the database. Add real PostgreSQL round-trip coverage with long IDs and values and non-null observation confidence. Preserve existing databases through an additive migration rather than destructive reset.

## Follow-up

DLK-M3-007 is the bounded correction packet. Durable HTTP work remains gated on acceptance. Existing test counts do not invalidate the reproduced guard and schema defects. No implementation code was changed during review.
