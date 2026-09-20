---
task_id: DLK-M3-006
title: Establish PostgreSQL persistence foundation and immutable initial-analysis storage
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-005]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-006: Establish PostgreSQL persistence foundation and immutable initial-analysis storage

## Objective

Establish the first real PostgreSQL persistence boundary for Dispense Lens and prove that one prepared diagnostic case plus its structured observations and initial analysis revision can be written atomically and read back without losing diagnostic meaning.

This is a persistence-foundation task, not a durable HTTP workflow task. The existing `POST /api/v1/diagnoses` endpoint must remain stateless and behaviorally unchanged. The next task will expose durable create/retrieve behavior only after this schema, migration, configuration, and repository contract is accepted.

The storage design must preserve the project's core investigation guarantees from the first persisted record:

- original case text and known process context are retained;
- structured observations retain stable IDs and provenance rather than being collapsed into free text;
- the analysis is stored as revision `1` and is append-oriented/immutable by repository contract;
- the full structured diagnosis result is recoverable, including ranked causes, evidence traces, next question/check, explanation, state, warnings, and revision content;
- root-cause confirmation and issue recovery remain separate future records and must not be collapsed into one status field;
- PostgreSQL is the persistence target. Do not silently substitute SQLite or an in-memory database.

## Current evidence

Verified/planner evidence:

- DLK-M3-005 was accepted by the planner at implementation commit `9d7a6e06c3d25b6566bc013afe79f6d8f00d367d`; focused API tests passed 13/13 and the full backend suite passed 24/24.
- The accepted DLK-M3-005 review record and accepted `QUEUE.md` update are currently expected to be uncommitted handoff artifacts and should be preserved unchanged for inclusion in this task's atomic implementation commit, per `.agents/handoff/PROJECT.md`.
- `.agents/handoff/NEXT-STEPS.md` places PostgreSQL persistence immediately after the accepted initial diagnosis API and requires the persistence contract to be settled before a durable-case API is implemented.
- `database/schema.sql`, `docs/database/erd.md`, `backend/app/db/database.py`, `backend/app/db/session.py`, `backend/app/db/seed.py`, `backend/app/core/config.py`, and the files under `backend/app/models/` are currently placeholders/empty in the planner snapshot.
- `backend/pyproject.toml` currently declares FastAPI/Uvicorn plus test dependencies only; no relational ORM, PostgreSQL driver, or migration tool is established yet.
- The engine's internal domain contracts live in `backend/app/schemas/diagnosis.py`. Relevant persisted data includes `StructuredCase`, `Observation`, `AnalysisRevision`, `CandidateCause`, evidence traces, `DiagnosisResult`, and `IssueCondition`.
- `DiagnosticEngine.diagnose(StructuredCase)` mutates the provided structured case by adding extracted observations and appending the new `AnalysisRevision`. This allows persistence to capture the actual observations used by the engine without changing Member 2's diagnostic logic.
- The current public endpoint remains intentionally stateless; its transient `case_id` is not retrievable.
- The project requirements explicitly preserve observations/provenance, analysis revisions, and independent cause-confirmation/recovery semantics.
- No accepted database contract exists yet. This task is authorized to establish the bounded foundation described below.

Before editing, Gemini must inspect the live repository/branch and reconcile these facts with the current checkout. If the accepted DLK-M3-005 state or relevant files differ materially, stop and report the discrepancy rather than guessing.

## Requirements

- Use PostgreSQL as the only supported relational database for this persistence contract.
- Establish SQLAlchemy 2.x ORM/session infrastructure, Alembic migrations, and the PostgreSQL `psycopg` driver.
- Add a reproducible local PostgreSQL development service using Docker Compose, with clearly non-production local credentials only. No real secret may be committed.
- Add a documented `.env.example` or equivalent example configuration for `DATABASE_URL`; actual `.env` files remain prohibited.
- Database configuration must be lazy enough that importing/running the existing stateless FastAPI application does not require PostgreSQL to be running. Persistence operations and migration commands must fail clearly when database configuration is absent/invalid rather than falling back to SQLite.
- Make Alembic the authoritative schema-evolution mechanism. Do not build a second competing migration system in `database/schema.sql`.
- Create a minimal relational contract that supports the accepted next workflow without pre-implementing later features:
  - one case record;
  - zero or more structured observation records belonging to that case;
  - one or more append-only analysis-revision records belonging to that case, with revision `1` used in this task.
- The case record must preserve at least:
  - stable `case_id`;
  - original description;
  - material, dispensing method, and machine context when supplied;
  - current identified defect code/name when available;
  - current issue condition;
  - creation timestamp.
- Each observation record must preserve at least:
  - owning `case_id`;
  - stable observation ID from the domain model;
  - observation type and value;
  - original text when present;
  - statement type;
  - evidence source/provenance;
  - confidence when present;
  - observation timestamp;
  - the first analysis revision in which the observation is present (revision `1` for this task).
- Each analysis revision must preserve at least:
  - owning `case_id`;
  - revision number;
  - analysis timestamp;
  - defect code at that revision;
  - issue condition at that revision;
  - the complete `DiagnosisResult` snapshot as PostgreSQL JSONB, serialized through the existing Pydantic contract in JSON mode so enums/datetimes are represented consistently;
  - uniqueness of `(case_id, revision_number)`.
- Do not flatten the diagnosis snapshot so aggressively that evidence provenance, evidence relation/strength/contribution, missing evidence, score breakdowns, cause conclusions, next question, next check, warnings, explanation, or revision-change information is lost.
- Keep storage append-oriented:
  - provide an initial-save operation and read/query operations needed to verify it;
  - do not add repository update/delete methods for analysis revisions;
  - a second write of the same `(case_id, revision_number)` must not silently overwrite the existing revision.
- Persist a prepared `StructuredCase` and corresponding `DiagnosisResult` atomically. If any part of the initial case/observation/revision write fails, no partial new case may remain committed.
- The repository/service must reject a mismatched case/result pair (for example, `case.case_id != result.case_id`) before committing.
- The repository/service must reject an initial persistence call that does not represent revision `1` or whose `DiagnosisResult.analysis_revision` is absent, because this task stores a completed initial diagnosis, not an unanalysed case shell.
- Preserve timezone-aware timestamps. PostgreSQL timestamp columns representing domain times must use timezone-aware semantics.
- Use PostgreSQL JSONB for genuinely structured/variable fields such as machine context and the immutable diagnosis snapshot; do not stringify JSON into text columns.
- Do not seed production-like or synthetic diagnostic cases in this task. The persistence tests must create their own isolated data.
- Add focused integration tests against a real PostgreSQL instance. SQLite/in-memory substitutes do not satisfy the acceptance criteria.
- Tests must prove at minimum:
  1. Alembic can upgrade a fresh PostgreSQL database to `head`.
  2. A real supported diagnosis prepared through the existing engine can be saved as case + observations + revision 1 and reconstructed/read back with semantic parity for the persisted fields.
  3. Extracted observations generated from a text-only diagnosis are persisted with their stable IDs/provenance, not merely the user's raw description.
  4. The stored revision snapshot semantically matches the original `DiagnosisResult` JSON payload.
  5. Duplicate revision insertion cannot overwrite revision 1.
  6. A deliberately invalid initial write rolls back atomically so no partial case is left behind.
  7. Two different case IDs can be stored independently without identity leakage.
- Preserve all currently accepted stateless API behavior and the existing 24-test backend baseline.

### Authorized dependency decision

This task is explicitly authorized to add the following persistence dependencies, using current compatible stable major versions constrained as shown unless the live repository already has an equivalent accepted dependency:

- `SQLAlchemy>=2.0,<3.0`
- `alembic>=1.13,<2.0`
- `psycopg[binary]>=3.1,<4.0`

Do not add an additional ORM, async database stack, Supabase SDK, pgvector, Redis, repository framework, settings framework, or test-container library in this task. Standard-library environment handling is sufficient unless an existing accepted configuration abstraction already exists.

## Interfaces and data contracts

### Public HTTP interface

No public API change is authorized.

`POST /api/v1/diagnoses` remains stateless and must continue returning the accepted `DiagnosisResult` contract. It must not begin writing to PostgreSQL under DLK-M3-006.

### Database contract

The exact Python class/table names are private implementation details, but the resulting migration must implement the following conceptual entities and constraints.

#### Case

One row per diagnostic investigation.

Required semantics:

- `case_id`: UUID-compatible identifier, primary key. The persisted value must preserve the existing domain `case_id` generated before persistence.
- `description`: original technician description; non-null string, empty allowed only if the diagnosis was valid through structured observations.
- `material`: nullable string.
- `method`: nullable string.
- `machine_context`: nullable JSONB object.
- `defect_code`: nullable string because an unidentifiable result may exist at engine level, although this task's success-path fixture should use an identifiable case.
- `defect_name`: nullable string.
- `issue_condition`: non-null string preserving the domain enum value.
- `created_at`: timezone-aware timestamp preserving the structured case timestamp.

Do not add a combined `resolved/cause_confirmed` boolean. Explicit cause confirmation and recovery verification remain separate later entities.

#### Observation

One row per structured observation associated with a case.

Required semantics:

- owning `case_id` foreign key with integrity enforcement;
- `observation_id` preserving the domain observation ID;
- uniqueness at least within a case (`case_id`, `observation_id`);
- `observation_type`;
- `value`;
- nullable `original_text`;
- `statement_type`;
- `source`/provenance;
- nullable `confidence`;
- timezone-aware observation timestamp;
- `first_seen_revision` positive integer, `1` for this task.

Client/domain observation IDs are strings today; do not narrow the storage contract to a PostgreSQL UUID type unless the live domain validator guarantees UUID-only IDs. Preserve compatibility with the current accepted `Observation` model.

#### Analysis revision

One append-only snapshot per analysis pass.

Required semantics:

- owning `case_id` foreign key;
- `revision_number` positive integer;
- unique constraint on (`case_id`, `revision_number`);
- timezone-aware analysis timestamp;
- nullable defect code;
- non-null issue condition;
- non-null JSONB `result_snapshot` containing `DiagnosisResult.model_dump(mode="json")` or a semantically equivalent serialization with no diagnostic fields removed.

For DLK-M3-006, only revision 1 is written by the repository's initial-save operation. Design the constraint/layout so later tasks can append revision 2+ without rewriting revision 1.

### Persistence boundary

Provide a small internal repository/service boundary that supports at least:

- atomically save one prepared `StructuredCase` with its corresponding initial `DiagnosisResult`;
- read the persisted case and its observations;
- read a named analysis revision (at least revision 1) and its JSON snapshot;
- optionally list the case's revision numbers if that is the simplest clean implementation.

The persistence boundary must not invoke private diagnostic scoring/ranking logic itself. Tests may prepare a `StructuredCase`, call the existing `DiagnosticEngine.diagnose(case)`, then pass the mutated `case` plus returned `DiagnosisResult` into persistence. This captures the engine-generated observations/revision without modifying Member 2's engine.

### Local database configuration

Provide a reproducible local PostgreSQL service, preferably PostgreSQL 16, through repository Docker Compose configuration. Local-only credentials may be explicit defaults but must be labelled as development-only. Application/migration database access must use `DATABASE_URL` from the environment.

Do not commit `.env`; commit only `.env.example` or equivalent documentation.

## Allowed paths

- `backend/pyproject.toml`
- `backend/alembic.ini`
- `backend/alembic/**`
- `backend/app/core/config.py`
- `backend/app/db/**`
- `backend/app/models/**`
- `backend/tests/integration/test_persistence.py`
- `backend/tests/conftest.py` if a narrowly scoped PostgreSQL fixture is required
- `backend/README.md`
- `docs/database/erd.md`
- `database/schema.sql` only to add a short notice that Alembic migrations are authoritative; do not maintain a duplicate hand-written schema here
- `.env.example`
- `compose.yaml`
- `.agents/handoff/reviews/DLK-M3-005-review.md` - include the accepted planner review unchanged if it is still an uncommitted handoff artifact
- `.agents/handoff/tasks/DLK-M3-006-postgresql-persistence-foundation.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/NEXT-STEPS.md` - status wording for DLK-M3-006 only; do not release later tasks

If the live repository uses an already-established equivalent location for Compose/environment configuration, stop and ask the planner before moving the contract to materially different paths.

## Prohibited scope

- Do not modify `backend/app/api/diagnoses.py`, request/response schemas, route paths, HTTP status codes, or other public API behavior.
- Do not make `POST /api/v1/diagnoses` persistent yet.
- Do not add create-case, get-case, history, answer, check-result, confirmation, recovery, report, image, retrieval, authentication, or frontend endpoints.
- Do not modify diagnostic engine logic, scoring, evidence semantics, question/check selection, symptom extraction, knowledge JSON, or Member 2-owned behavior.
- Do not implement explicit cause-confirmation or recovery-verification tables/flows yet; their human-confirmation semantics are intentionally deferred. The schema must merely avoid coupling them.
- Do not implement question-answer persistence, check-result persistence, report persistence, image persistence, historical-case retrieval, embeddings, pgvector, CV, LLM integration, analytics, or seed data.
- Do not introduce SQLite fallback, in-memory production persistence, MongoDB, Supabase SDK, another ORM, or another migration framework.
- Do not introduce async SQLAlchemy in this task unless the live backend already adopted an accepted async database contract. The current FastAPI endpoint does not require a database, and a small synchronous persistence boundary is sufficient for this milestone.
- Do not commit real credentials, `.env`, PostgreSQL data volumes, generated Alembic cache files, test databases, coverage output, virtual environments, or other generated artifacts.
- Do not rewrite accepted DLK-M3-005 review/history.
- Do not push, merge, rebase a shared branch, create/update a pull request, or modify `main`.

## Implementation guidance

1. Perform implementation-handoff preflight. Confirm branch `backend-database`, inspect `git status`, recent commits, and commit `9d7a6e06c3d25b6566bc013afe79f6d8f00d367d`. Confirm DLK-M3-005 is accepted and that the only expected uncommitted overlap consists of planner handoff artifacts (`DLK-M3-005-review.md`, accepted queue update, this ready task/queue update). Preserve unrelated changes and stop if any overlap this task.
2. Set DLK-M3-006 and `QUEUE.md` to `in_progress` before implementation.
3. Add only the authorized SQLAlchemy/Alembic/psycopg dependencies. Reinstall the editable backend environment and record the resolved versions in the implementation report.
4. Establish lazy `DATABASE_URL` configuration. The application must still import and existing stateless tests must still run when no database URL is configured. Database creation/session/migration operations must fail with a clear configuration error if persistence is invoked without a PostgreSQL URL.
5. Add a local PostgreSQL Compose service and `.env.example`. Do not automatically load or commit secrets. Document the exact Windows-friendly startup/stop/migration commands in `backend/README.md`.
6. Define the minimal ORM schema and first Alembic migration for case, observation, and analysis revision. Prefer database-level foreign keys, uniqueness, non-null constraints, positive revision/check constraints where appropriate, PostgreSQL JSONB, and timezone-aware timestamps.
7. Keep Alembic as the schema authority. If `database/schema.sql` is touched, make it a short pointer to Alembic rather than copying all DDL.
8. Implement a small persistence repository/service. Validate case/result identity and revision-1 preconditions before opening/committing the transaction where practical. Use one transaction for case + all observations + revision 1.
9. For the success-path integration test, create a `StructuredCase` with a text description that the current accepted engine can identify, call `DiagnosticEngine.diagnose(case)`, and assert that the same mutated case observations and returned result are persisted. This ensures the test covers engine-generated structured observations rather than only caller-provided ones.
10. Reconstruct/read back persisted data through the repository/session layer and compare semantic values, not ORM object identity. Compare the JSONB result snapshot against `DiagnosisResult.model_dump(mode="json")` exactly except only if PostgreSQL/JSON numeric representation makes a narrowly documented normalization necessary; do not normalize away diagnostic fields.
11. Add a duplicate-revision test that proves an existing revision cannot be silently overwritten. Add an atomicity test that intentionally violates a database constraint within a brand-new case write and then verifies that the new case itself was rolled back.
12. Ensure test isolation. Tests may delete only records they themselves create or use transaction rollback/truncation confined to the local test database. Never run destructive cleanup against an unverified non-local database. Add a safety check in test setup so destructive fixture cleanup requires a clearly local/test database name or an explicit test marker in the URL.
13. Run the migration from a fresh/empty local PostgreSQL database, then focused persistence tests, the existing diagnosis/health API tests, and the full backend suite.
14. Update `docs/database/erd.md` with the implemented minimal entities, keys, relationships, JSONB snapshot rationale, append-only revision rule, and explicitly deferred separate cause-confirmation/recovery entities.
15. Complete this task's implementation report, set task/queue status to `implemented`, inspect the staged diff and staged file list, and create one atomic local commit only after every required check passes.

## Acceptance criteria

- [x] PostgreSQL persistence dependencies are added using the authorized stack only: SQLAlchemy 2.x, Alembic, and psycopg 3; no SQLite fallback or second ORM/migration system is introduced.
- [x] A reproducible local PostgreSQL development service and safe example `DATABASE_URL` configuration are documented without committing real secrets.
- [x] Importing the FastAPI application and running the pre-existing stateless API/engine tests does not require PostgreSQL; invoking persistence/migrations without valid PostgreSQL configuration fails clearly instead of silently using another database.
- [x] Alembic can upgrade a fresh local PostgreSQL database from empty state to `head` and creates the implemented case, observation, and analysis-revision contract with foreign-key and uniqueness constraints.
- [x] The persisted case preserves case ID, original description, material/method/machine context, identified defect information, issue condition, and timezone-aware creation timestamp.
- [x] Structured observations are stored as separate records preserving stable observation IDs, observation type/value, original text, statement type, provenance/source, confidence, timestamp, and first-seen revision.
- [x] The success-path persistence test uses the real accepted `DiagnosticEngine` with a `StructuredCase` and proves engine-generated text-extraction observations are persisted, not just the raw description.
- [x] Revision 1 is stored as an append-oriented record with a unique `(case_id, revision_number)` constraint and a non-null JSONB snapshot semantically equal to the original `DiagnosisResult` JSON serialization.
- [x] The stored diagnosis snapshot retains cause scores/conclusions, supporting/contradicting/neutral evidence including provenance/relation/strength/contribution, missing evidence, score breakdowns, next question/check, explanation, issue condition, warnings, and analysis-revision details when present.
- [x] Persistence rejects mismatched case/result IDs and rejects attempts to use the initial-save operation with a missing/non-1 analysis revision.
- [x] A duplicate revision cannot silently overwrite revision 1.
- [x] A deliberately failing brand-new initial save rolls back atomically so no partial case/observation/revision remains.
- [x] Two separate case IDs can be persisted and read independently without sharing observations or revision snapshots.
- [x] The schema/documentation explicitly avoids coupling cause confirmation with recovery and leaves those as separate deferred entities.
- [x] `POST /api/v1/diagnoses` remains stateless and its accepted request/response/error behavior is unchanged.
- [x] Focused persistence tests, existing diagnosis/health integration tests, and the complete backend suite pass against the documented local setup with actual counts/warnings recorded.
- [x] No unrelated files, real secrets, generated PostgreSQL data, environments, or out-of-scope feature work are staged or committed.

## Verification

Use the established backend virtual environment on Windows. If Docker is unavailable but a local PostgreSQL 16+ server is already installed, the same checks may be run against a clearly local disposable/test database via `DATABASE_URL`; do not substitute SQLite. Record which path was used.

From repository root:

1. `docker compose config`
2. `docker compose up -d postgres`

From `backend/`:

3. `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`
4. Set `DATABASE_URL` for the current shell to the documented local/test PostgreSQL URL from `.env.example` (do not create or commit `.env` merely for verification).
5. `.\.venv\Scripts\python.exe -m alembic upgrade head`
6. `.\.venv\Scripts\python.exe -m alembic current`
7. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_persistence.py`
8. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_diagnosis_api.py tests/integration/test_health_api.py`
9. `.\.venv\Scripts\python.exe -m pytest -q`
10. `.\.venv\Scripts\python.exe -c "from app.main import app; assert '/api/v1/diagnoses' in app.openapi()['paths']; print('stateless diagnosis API import/OpenAPI unchanged')"`

From repository root:

11. `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-006-postgresql-persistence-foundation.md`
12. `git diff --check`
13. Inspect `git status --short`, `git diff --cached`, and `git diff --cached --name-only` before committing. Only authorized task paths plus the accepted pending DLK-M3-005 handoff record may be staged.

After verification, stop the local service if it was started only for the task:

14. `docker compose down`

Do not use `docker compose down -v` as a routine verification command because deleting volumes is destructive. If the test database must be reset for the fresh-migration check, use a clearly local disposable database and document the bounded reset action in the implementation report.

Record exact command outcomes, package versions, migration revision, test counts, warnings, and any environment limitation. A required persistence verification that cannot run against real PostgreSQL means the task is `blocked`, not `implemented`.

## Planner decision boundaries

Return to the planner before:

- changing the conceptual case/observation/analysis-revision database contract above;
- replacing PostgreSQL, SQLAlchemy, Alembic, or psycopg, or adding another material dependency;
- changing public API behavior or making the existing diagnosis route persistent;
- modifying Member 2's diagnosis engine/domain meaning to simplify persistence;
- narrowing accepted observation IDs/provenance or dropping diagnostic fields from the stored snapshot;
- adding cause-confirmation/recovery semantics, answer/check persistence, retrieval/vector storage, images, reports, auth, or frontend work;
- using a destructive migration/reset against any non-disposable database;
- moving database configuration to a materially different architecture than the bounded environment-variable approach authorized here;
- broadening task scope because a persistence test exposes an engine/domain defect. In that case, report the smallest reproducible mismatch and stop.

## Git instructions

Create one atomic local commit after all required checks pass. Include the accepted but previously uncommitted DLK-M3-005 review/queue handoff records unchanged if they are still pending, plus the completed DLK-M3-006 packet and implementation files.

Do not push, merge, rebase a shared branch, create/update a pull request, or change `main`.

Proposed commit message: `feat(db): establish postgresql persistence foundation`

## Implementation report

### Summary

Established the PostgreSQL persistence foundation for DispenseLens/Dispense Lens:
- Installed authorized persistence dependencies: `SQLAlchemy 2.0.52`, `Alembic 1.20.0`, and `psycopg 3.3.5` (binary);
- Configured local PostgreSQL 16 development service in `compose.yaml` and safe configuration template in `.env.example`;
- Implemented lazy database configuration in `app.core.config`, ensuring that importing the app or running stateless tests requires no active database and explicitly raises `ValueError` if SQLite or other unsupported database schemes are specified;
- Defined relational ORM models for `cases`, `case_observations`, and `analysis_revisions` in `app.models.case`;
- Established Alembic migrations as authoritative schema evolutions with migration `0001_initial_persistence`;
- Implemented `CaseRepository` in `app.db.repository` providing atomic initial persistence for a `StructuredCase` and initial `DiagnosisResult` (Revision 1), reading back cases, observations, and revision snapshots, and enforcing precondition checks and immutability rules;
- Preserved strict architectural separation: root-cause confirmation and issue recovery remain decoupled deferred entities;
- Verified against real PostgreSQL instance with 10 focused persistence integration tests, the 13 diagnosis/health tests, and all 34 total backend tests passing.

### Files changed

- `.agents/handoff/QUEUE.md`: Updated active task DLK-M3-006 status to `implemented`.
- `.agents/handoff/NEXT-STEPS.md`: Updated sequence table to show DLK-M3-006 implemented.
- `.agents/handoff/tasks/DLK-M3-006-postgresql-persistence-foundation.md`: Updated task status to `implemented` and filled in implementation report.
- `backend/pyproject.toml`: Added authorized dependencies `sqlalchemy>=2.0,<3.0`, `alembic>=1.13,<2.0`, `psycopg[binary]>=3.1,<4.0`.
- `backend/alembic.ini`: Configured Alembic migration runner.
- `backend/alembic/env.py`: Online and offline migration runner using lazy `get_database_url()`.
- `backend/alembic/script.py.mako`: Migration script template.
- `backend/alembic/versions/0001_initial_case_persistence.py`: Initial migration establishing `cases`, `case_observations`, and `analysis_revisions` tables.
- `backend/app/core/config.py`: Lazy PostgreSQL connection URL retriever and validator prohibiting non-PostgreSQL databases.
- `backend/app/db/__init__.py`: Package exports for database engine, session, and repository.
- `backend/app/db/database.py`: Declarative `Base` and lazy `get_engine()` / `reset_engine()`.
- `backend/app/db/repository.py`: `CaseRepository` implementing atomic initial persistence and read queries.
- `backend/app/db/seed.py`: Scope documentation clarifying that seed data is not used for this task.
- `backend/app/db/session.py`: Session management, `session_scope()`, and `get_session_factory()`.
- `backend/app/models/__init__.py`: Exporting `CaseModel`, `ObservationModel`, `AnalysisRevisionModel`.
- `backend/app/models/case.py`: SQLAlchemy mapped models for `cases`, `case_observations`, `analysis_revisions`.
- `backend/tests/integration/test_persistence.py`: 10 comprehensive integration tests against real PostgreSQL.
- `backend/README.md`: Documented local Docker Compose PostgreSQL setup, environment configuration, migration commands, and persistence tests.
- `compose.yaml`: Local PostgreSQL 16 service configuration.
- `.env.example`: Safe template for `DATABASE_URL`.
- `database/schema.sql`: Short pointer notice designating Alembic as authoritative schema manager.
- `docs/database/erd.md`: ERD Mermaid diagram, column specifications, constraints, JSONB snapshot rationale, and architectural guarantees.

### Decisions made

1. **Case ID Representation**: Mapped `case_id` to PostgreSQL native `UUID(as_uuid=False)` in SQLAlchemy, ensuring UUID validation at the database layer while preserving string representations in Pydantic domain models.
2. **Observation ID String Support**: Kept `observation_id` as `VARCHAR(64)` per task packet instructions rather than narrowing to UUID, retaining domain model flexibility.
3. **Surrogate PK for Auxiliary Tables**: Used surrogate autoincrement integer primary keys on `case_observations` and `analysis_revisions` while strictly enforcing business uniqueness via `uq_case_observations_case_id_obs_id` on `(case_id, observation_id)` and `uq_analysis_revisions_case_id_revision_number` on `(case_id, revision_number)`.
4. **Append-Only Immutability**: Enforced at both database level (unique constraint on `(case_id, revision_number)`) and repository layer (no update/delete methods for analysis revisions; initial persistence restricted strictly to revision 1).
5. **No SQLite Fallback**: Explicitly rejected SQLite and in-memory databases with clear exceptions (`ValueError`) in `get_database_url()`.
6. **Safety Precheck**: Implemented a database URL validator (`_assert_safe_test_database`) requiring localhost/test markers before running destructive fixture cleanups.

### Verification results

1. `docker compose config`: Exited with code 0; valid Docker Compose specification.
2. `docker compose up -d postgres`: Started container `dispenselens-postgres` with `postgres:16-alpine` (healthy on port 5432).
3. `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`: Successfully installed `sqlalchemy-2.0.52`, `alembic-1.20.0`, `psycopg-3.3.5`, `psycopg-binary-3.3.5`.
4. `.\.venv\Scripts\python.exe -m alembic upgrade head`: Applied migration `0001_initial_persistence` successfully.
5. `.\.venv\Scripts\python.exe -m alembic current`: Reported `0001_initial_persistence (head)`.
6. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_persistence.py`: 10 passed in 1.14s.
7. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_diagnosis_api.py tests/integration/test_health_api.py`: 13 passed, 2 warnings in 0.67s.
8. `.\.venv\Scripts\python.exe -m pytest -q`: 34 passed, 2 warnings in 1.73s (full backend suite: 24 baseline + 10 persistence).
9. `.\.venv\Scripts\python.exe -c "from app.main import app; assert '/api/v1/diagnoses' in app.openapi()['paths']; print('stateless diagnosis API import/OpenAPI unchanged')"`: Printed `stateless diagnosis API import/OpenAPI unchanged` without requiring `DATABASE_URL`.
10. `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-006-postgresql-persistence-foundation.md`: Returned `VALID`.
11. `git diff --check`: Exited with code 0 (clean, no whitespace or formatting errors).

### Limitations and follow-up

- `POST /api/v1/diagnoses` remains stateless and does not persist cases, per packet boundaries.
- Case persistence is currently internal via `CaseRepository`; durable HTTP CRUD endpoints, answer submissions, check results, and cause confirmation flows are deferred to subsequent tasks (DLK-M3-007+).
- Two external dependency deprecation warnings (`starlette.testclient` and `anyio.abc.BlockingPortal`) were present in the baseline test run and do not impact functionality.

### Proposed commit message

`feat(db): establish postgresql persistence foundation`
