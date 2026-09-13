---
task_id: DLK-M3-009
title: Expose durable diagnosed-case create and retrieve API
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-008]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-009: Durable diagnosed-case create/retrieve API

## Objective

Expose the accepted PostgreSQL persistence foundation through a minimal durable HTTP API.

A client must be able to:

1. submit a new diagnostic case;
2. run the existing deterministic diagnostic engine;
3. persist the case, interpreted observations, and immutable revision-1 diagnosis atomically; and
4. retrieve the persisted case and its initial diagnosis by case ID.

Preserve the existing stateless `POST /api/v1/diagnoses` endpoint unchanged.

This task does **not** implement follow-up answers, troubleshooting-result submission, cause confirmation, recovery verification, reports, authentication, LLM/CV, historical retrieval, or frontend integration.

## Current evidence

DLK-M3-008 is accepted at commit:

`2ff7a8be5a93fc88dac5954b306ed1436c73ceda`

Accepted persistence behavior includes:

- PostgreSQL-backed `CaseRepository`;
- atomic case + observations + revision-1 persistence;
- append-oriented immutable analysis revisions;
- complete `DiagnosisResult` snapshot persistence;
- unrestricted valid domain strings round-tripping without truncation;
- accepted local PostgreSQL test-destination safety;
- unchanged stateless `POST /api/v1/diagnoses`.

## Requirements

### Product/API scope

Implement exactly two durable endpoints.

### `POST /api/v1/cases`

Must:

- accept the same diagnostic input semantics as `POST /api/v1/diagnoses`;
- construct the existing `StructuredCase`;
- invoke the existing `DiagnosticEngine`;
- persist the mutated case, generated/client observations, and revision-1 diagnosis through the accepted repository;
- return `201 Created`;
- return the persisted durable case representation;
- remain atomic: no partial case may survive a failed persistence operation.

Do not duplicate diagnostic logic inside the route.

### `GET /api/v1/cases/{case_id}`

Must:

- load the persisted case by canonical case ID;
- return persisted case context;
- return persisted observations with provenance;
- return persisted immutable revision-1 diagnosis;
- return `404` for an unknown case;
- perform **no diagnostic recalculation**.

The GET response must reflect stored state, not a fresh engine run.

## Interfaces and data contracts

### Request contract

Prefer reuse of the existing diagnosis request schema, or extract a shared schema only if generated OpenAPI behavior for `/api/v1/diagnoses` remains unchanged.

Preserve current diagnosis input semantics, including applicable existing fields such as:

- `defect_code`
- `problem_description`
- `material`
- `method`
- `machine_context`
- client-supplied observations already accepted by the diagnosis API

Do not introduce new required product fields.

### Durable response contract

Define one explicit durable-case response model.

At minimum expose:

- `case_id`
- persisted case context/input fields
- persisted observations, including provenance and other existing observation metadata
- persisted initial diagnosis/revision snapshot
- persisted creation timestamp if already available in the accepted schema

Preserve domain enums/types rather than inventing unrelated strings.

The initial diagnosis must remain semantically equivalent to the `DiagnosisResult` created by the engine at POST time.

### Status/error contract

Use:

- `201 Created` — successful create
- `200 OK` — successful retrieve
- `404 Not Found` — unknown case
- normal FastAPI/Pydantic `422` behavior for malformed input/path values
- `500 Internal Server Error` — unexpected diagnosis/persistence failure

Error responses must not expose:

- database URLs
- usernames/passwords
- SQL
- stack traces
- internal filesystem paths
- other secrets

## Architecture requirements

Expected orchestration:

`HTTP request -> validated schema -> StructuredCase -> DiagnosticEngine -> CaseRepository -> HTTP response`

The route must not reimplement:

- defect identification
- evidence extraction/reasoning
- cause ranking
- question selection
- troubleshooting planning
- cause-state logic
- issue-condition logic

### Persistence source of truth

After successful POST:

- subsequent GET of the returned `case_id` must reconstruct the same durable semantic state;
- retrieval must not call `DiagnosticEngine.diagnose()`;
- retrieval must not mutate observations, revisions, or case state.

### Transaction boundary

Creation remains atomic across:

- case
- observations
- revision 1 / diagnosis snapshot

If persistence fails after diagnosis succeeds, no partial durable case may remain.

### Existing stateless diagnosis API

`POST /api/v1/diagnoses` remains stateless and must not require a DB connection when used independently.

Do not alter its public request/response contract.

## Allowed paths

- `backend/app/api/routes/cases.py` or repository-equivalent route module
- existing API route registration module only as needed
- `backend/app/schemas/case.py` or equivalent
- existing diagnosis schema module only for safe schema reuse without public regression
- `backend/app/db/repository.py` only for the smallest read/create support required
- `backend/app/db/session.py` only if a FastAPI session dependency is genuinely required
- `backend/app/models/__init__.py` only if required for imports
- `backend/tests/integration/test_case_api.py`
- existing API integration tests only when needed for regression proof
- `docs/api/api-spec.md`
- `backend/README.md` only for a small local usage update if required
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/NEXT-STEPS.md` only to record milestone progress
- `.agents/handoff/reviews/DLK-M3-008-review.md` (include unchanged)
- `.agents/handoff/tasks/DLK-M3-009-durable-case-api.md`

Return to the planner before editing outside this scope.

## Prohibited scope

Do not implement:

- follow-up answer submission
- troubleshooting-check result submission
- revision 2+ workflow
- root-cause confirmation endpoint
- recovery/verification endpoint
- report/PDF generation
- image/CV
- LLM interpretation
- historical/similar-case retrieval
- pgvector
- authentication/authorization
- frontend integration
- list/pagination APIs
- update/delete APIs
- generic CRUD infrastructure
- background workers/WebSockets
- new dependencies
- schema/migration changes

If a migration/schema change appears necessary, stop and return the issue to the planner first.

Do not weaken the accepted PostgreSQL test-safety policy.

## Implementation guidance

1. Run implementation-handoff preflight.
2. Confirm DLK-M3-009 is the only `ready` task.
3. Reuse the accepted repository path from DLK-M3-006/007/008.
4. Define the durable response contract first.
5. Implement `POST /api/v1/cases`.
6. Implement `GET /api/v1/cases/{case_id}` using persisted state only.
7. Add real PostgreSQL API integration tests.
8. Prove `/api/v1/diagnoses` remains stateless and DB-independent.
9. Update API documentation using executable behavior.
10. Run focused and full verification.
11. Complete the task report and create one atomic local commit.

## Acceptance criteria

### POST

- [x] `POST /api/v1/cases` returns `201`.
- [x] Response contains a persisted canonical `case_id`.
- [x] Existing real `DiagnosticEngine` is used.
- [x] Engine-generated observations are persisted with provenance.
- [x] Valid client-supplied observations are persisted with provenance.
- [x] Revision 1 persists the complete diagnosis snapshot.
- [x] Returned diagnosis is semantically equivalent to the engine result for that request.
- [x] Successful creation produces exactly one case and exactly one initial analysis revision.
- [x] An induced persistence failure leaves no partial case/observations/revision.
- [x] Two identical independent POSTs may create distinct cases; no cross-request state sharing occurs.

### GET

- [x] Existing case returns `200`.
- [x] GET returns persisted context, observations/provenance, and revision-1 diagnosis.
- [x] GET does not call the diagnostic engine.
- [x] GET after POST is semantically consistent with POST.
- [x] Unknown valid case ID returns `404`.
- [x] GET does not mutate case state, observations, or revision count.

### Regression/security

- [x] Existing `/api/v1/diagnoses` remains stateless and behaviorally unchanged.
- [x] Existing diagnosis, health, persistence, and DB-safety tests pass.
- [x] Errors leak no credentials, SQL, DB URLs, or stack traces.
- [x] No migration/schema change occurs.
- [x] Only authorized files change.
- [x] No remote Git operation occurs.

## Required PostgreSQL integration scenarios

At minimum cover:

1. **Create + retrieve happy path**
   - POST valid case
   - expect `201`
   - GET returned `case_id`
   - assert semantic parity of context, observations/provenance, diagnosis and revision

2. **Generated observation persistence**
   - choose input that causes the real engine to generate structured observations
   - verify exact persisted observation semantics after GET

3. **Client-supplied observation persistence**
   - submit an observation through the existing contract
   - verify durable round trip without provenance loss

4. **Long-string regression**
   - valid observation ID >64 characters
   - at least one other accepted unrestricted long string
   - POST succeeds and GET round-trips exactly

5. **Missing case**
   - GET valid-but-unknown case ID
   - expect `404`

6. **No recalculation on GET**
   - spy/patch the appropriate diagnostic-engine seam after POST
   - GET succeeds without invoking diagnosis

7. **Atomic failure**
   - induce repository/transaction failure before successful commit
   - POST fails safely
   - verify no partial durable case remains

8. **Stateless diagnosis regression**
   - `/api/v1/diagnoses` still works without DB configuration/connection

## API documentation

Update `docs/api/api-spec.md` with:

- exact durable POST request
- exact `201` response
- exact durable GET response
- `404` behavior
- validation/error behavior
- explicit distinction between stateless `/api/v1/diagnoses` and durable `/api/v1/cases`
- examples verified against executable behavior

Do not label an example as real execution output unless it was actually captured from the API.

## Verification

Use the accepted verified local PostgreSQL test database.

From `backend/`:

1. Apply current migrations:
   `.\\.venv\\Scripts\\python.exe -m alembic upgrade head`
2. Durable case API:
   `.\\.venv\\Scripts\\python.exe -m pytest -q tests/integration/test_case_api.py`
3. Existing diagnosis + health APIs:
   `.\\.venv\\Scripts\\python.exe -m pytest -q tests/integration/test_diagnosis_api.py tests/integration/test_health_api.py`
4. Persistence:
   `.\\.venv\\Scripts\\python.exe -m pytest -q tests/integration/test_persistence.py`
5. Persistence safety:
   `.\\.venv\\Scripts\\python.exe -m pytest -q tests/unit/test_persistence_safety.py`
6. Complete backend suite:
   `.\\.venv\\Scripts\\python.exe -m pytest -q`
7. Unset/remove `DATABASE_URL` and prove stateless diagnosis import/OpenAPI remains available without DB connection.
8. Inspect OpenAPI and verify both durable routes plus the unchanged stateless route.

From repository root:

9. Validate task packet:
   `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-009-durable-case-api.md`
10. `git diff --check`
11. Inspect `git status`, staged names, and staged diff before commit.

If real PostgreSQL verification cannot run, mark the task `blocked`; do not substitute SQLite or mocks for required integration proof.

## Planner decision boundaries

Return to the planner before:

- changing database schema/migrations
- changing diagnostic engine/scoring semantics
- changing the existing stateless diagnosis contract
- adding dependencies
- defining follow-up/revision-2 APIs
- adding authentication
- implementing generic case CRUD
- changing case-ID semantics
- relaxing PostgreSQL safety rules

## Git instructions

After all acceptance criteria pass:

- complete the implementation report;
- set DLK-M3-009 and `QUEUE.md` to `implemented`;
- inspect staged file names/diff;
- create exactly one atomic local commit.

Proposed commit message:

`feat(api): add durable case create and retrieve endpoints`

Do not push, merge, rebase, create/update a PR, or modify `main`.

## Implementation report

Complete before the local commit.

### Summary

Implemented durable case endpoints `POST /api/v1/cases` and `GET /api/v1/cases/{case_id}` backed by PostgreSQL via `CaseRepository`. The create endpoint accepts diagnostic inputs identical to the initial diagnosis API, executes the deterministic `DiagnosticEngine`, atomically stores the case, extracted/client observations (with provenance), and immutable revision-1 diagnosis snapshot, and returns `201 Created`. The retrieve endpoint fetches persisted state by canonical case UUID, returning `200 OK` with complete semantic parity and guaranteed zero engine recalculation (`DiagnosticEngine.diagnose()` is never called). The existing stateless `POST /api/v1/diagnoses` and health endpoints remain completely decoupled, functioning without a database connection or `DATABASE_URL`.

### Files changed

- `backend/app/schemas/case.py` (new): Request and response models (`CreateCaseRequest`, `CaseObservationResponse`, `DurableCaseResponse`) with alias support and strict forbidden extra fields.
- `backend/app/api/cases.py` (modified): Route handlers for `POST /api/v1/cases` and `GET /api/v1/cases/{case_id}` with atomic session management, sanitized error reporting, and UUID validation.
- `backend/app/api/router.py` (modified): Registered `cases_router` under prefix `/cases` with tag `Cases`.
- `backend/tests/integration/test_case_api.py` (new): Comprehensive test suite covering all 8 required integration scenarios, OpenAPI validation, idempotency, atomic rollback, and stateless regression.
- `docs/api/api-spec.md` (modified): Added Section 3 detailing Durable Case Management with real PostgreSQL execution output, comparison table, and updated error handling.
- `backend/README.md` (modified): Documented test execution command and durable case endpoints.
- `.agents/handoff/NEXT-STEPS.md` (modified): Recorded DLK-M3-009 implementation status.
- `.agents/handoff/QUEUE.md` (modified): Set task status to `implemented`.
- `.agents/handoff/tasks/DLK-M3-009-durable-case-api.md` (modified): Checked acceptance criteria and added implementation report.

### API contract implemented

- `POST /api/v1/cases`:
  - Request: `CreateCaseRequest` supporting `description` (or `problem_description`), `material`, `method`, `machine_context`, `defect_code`, and `observations`. Forbids caller-supplied IDs or revision metadata (`extra = "forbid"`).
  - Response: `DurableCaseResponse` with HTTP `201 Created`. Exposes canonical `case_id`, stored context, persisted observations with provenance, and immutable `initial_diagnosis` (plus mirror `diagnosis` alias).
- `GET /api/v1/cases/{case_id}`:
  - Path parameter: `case_id` validated as UUID.
  - Response: `DurableCaseResponse` with HTTP `200 OK` loaded directly from repository without invoking diagnostic engine.
  - Returns `404 Not Found` for unknown case UUIDs.
  - Returns `422 Unprocessable Entity` for malformed UUID format.
- Error handling:
  - Unexpected internal errors return sanitized `500 Internal Server Error` without leaking stack traces, database URLs, credentials, or SQL.

### Persistence/transaction decisions

- Reused accepted `CaseRepository.save_initial_case()` to ensure a single atomic transaction across `cases`, `case_observations`, and `case_analysis_revisions`.
- Session is provided via FastAPI dependency `session: Session = Depends(get_db)`, with explicit `session.commit()` on success and `session.rollback()` in `except HTTPException:` / `except Exception:` handlers to guarantee no partial case records remain on failure.
- In `GET /api/v1/cases/{case_id}`, repository queries database directly and maps persisted models without invoking `DiagnosticEngine`.
- Session dependency `get_db` is evaluated lazily only for routes requiring database access, keeping `POST /api/v1/diagnoses` and `/api/v1/health` completely decoupled from database availability.

### Verification results

Note: Historical implementer-reported verification results from the DLK-M3-009 implementation run:
1. `alembic upgrade head`: Database schema confirmed at `0002_widen_unrestricted_strings`.
2. `tests/integration/test_case_api.py`: 13 passed in 1.66s.
3. `tests/integration/test_diagnosis_api.py tests/integration/test_health_api.py`: 13 passed in 1.03s.
4. `tests/integration/test_persistence.py`: 11 passed in 1.24s.
5. `tests/unit/test_persistence_safety.py`: 17 passed in 0.22s.
6. Complete backend test suite (`pytest -q`): 65 passed, 2 warnings in 2.52s.
7. Database-free isolation check: Stateless diagnosis and health tests pass without `DATABASE_URL` set (13 passed in 0.89s).
8. Real API execution captured and documented in `docs/api/api-spec.md`.

### Limitations and follow-up

- Only initial case creation and retrieval (Revision 1) are implemented in this milestone.
- Follow-up question answers, troubleshooting check findings, subsequent revisions (Revision 2+), root cause confirmation, recovery verification, reporting, and frontend integration remain for subsequent tasks.

### Proposed commit message

`feat(api): add durable case create and retrieve endpoints`
