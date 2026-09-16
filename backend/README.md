# DispenseLens Backend

Backend service for the DispenseLens competition prototype, built with FastAPI.

## Setup and Installation (Windows PowerShell)

Run all commands from the `backend/` directory:

1. Create a virtual environment:
   ```powershell
   python -m venv .venv
   ```

2. Upgrade pip:
   ```powershell
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   ```

3. Install editable package with development dependencies:
   ```powershell
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   ```

## Database Setup and Migrations (Local PostgreSQL)

DispenseLens uses PostgreSQL with SQLAlchemy 2.x and Alembic for relational persistence.

### 1. Start Local PostgreSQL Service

From the repository root:
```powershell
# Validate compose configuration
docker compose config

# Start PostgreSQL 16 service in background
docker compose up -d postgres

# Stop PostgreSQL service when finished
docker compose down
```

### 2. Configure Environment

Set `DATABASE_URL` in your shell (or copy `.env.example` to `.env` for local work, do NOT commit `.env`):
```powershell
$env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"
```

> **Note on Test Safety Policy:**
> Automated persistence tests enforce fail-closed destination validation on `DATABASE_URL`. Connections must target approved local test hosts (`localhost`, `127.0.0.1`, `::1`, `dispenselens-postgres`, `postgres`) and disposable test database names (`dispenselens`, `test`, `test_*`, `*_test`). All connection query parameters (such as `host`, `hostaddr`, `dbname`, or `service` overrides) are strictly prohibited on test URLs.

### 3. Apply Migrations

Run from the `backend/` directory:
```powershell
# Upgrade to latest revision
.\.venv\Scripts\python.exe -m alembic upgrade head

# Inspect current revision
.\.venv\Scripts\python.exe -m alembic current
```

## Running Tests

Run the test suite using pytest:

```powershell
# Run the focused health API test
.\.venv\Scripts\python.exe -m pytest tests/integration/test_health_api.py -q

# Run database test safety unit tests (connection-free)
.\.venv\Scripts\python.exe -m pytest tests/unit/test_persistence_safety.py -q

# Run focused PostgreSQL persistence integration tests
.\.venv\Scripts\python.exe -m pytest tests/integration/test_persistence.py -q

# Run durable case API integration tests (requires PostgreSQL)
.\.venv\Scripts\python.exe -m pytest tests/integration/test_case_api.py -q

# Run technician question-answer API integration tests (requires PostgreSQL)
.\.venv\Scripts\python.exe -m pytest tests/integration/test_question_answer_api.py -q

# Run troubleshooting check-result API integration tests (requires PostgreSQL)
.\.venv\Scripts\python.exe -m pytest tests/integration/test_check_result_api.py -q

# Run root-cause confirmation API integration tests (requires PostgreSQL)
.\.venv\Scripts\python.exe -m pytest tests/integration/test_cause_confirmation_api.py -q

# Run all backend tests
.\.venv\Scripts\python.exe -m pytest -q
```

## Running the Development Server

Start the local FastAPI development server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Interactive OpenAPI documentation is available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON specification: `http://127.0.0.1:8000/openapi.json`

## Health Check Endpoint

- **Endpoint:** `GET /api/v1/health`
- **Response:**
  ```json
  {
    "status": "ok",
    "service": "dispense-lens-api",
    "version": "0.1.0"
  }
  ```

### Scope and Limitations of the Health Endpoint

The `/api/v1/health` endpoint reports solely that the web service process is active, initialized, and responsive to HTTP requests.

It **does not** perform or verify:
- Database connectivity or query readiness
- External network connectivity
- Filesystem storage or disk availability
- AI, machine learning, or computer-vision inference readiness
- Auxiliary worker processes or background queues

## Initial Diagnosis Endpoint

- **Endpoint:** `POST /api/v1/diagnoses`
- **Description:** Stateless endpoint that accepts an initial dispensing problem description, material, dispensing method, and optional observations, executing Member 2's diagnostic engine to return ranked candidate causes, evidence assessments, and recommended follow-up questions/checks.
- **Contract & Scope:**
  - Stateless execution: no persistent database storage or session caching.
  - Generates an ephemeral `case_id` for the diagnostic run.
  - Caller cannot supply `case_id`, previous answers, or prior check results.
  - Returns `422 Unprocessable Entity` for empty evidence, defect code alone, unknown defect codes, or forbidden extra fields.
  - Returns sanitized `500 Internal Server Error` on unexpected engine errors without leaking internal stack traces or user payload data.
- **Full Specification:** See [API Specification](../docs/api/api-spec.md) for full schemas, field definitions, and execution payloads.

## Durable Case Endpoints

- **Endpoints:**
  - `POST /api/v1/cases` — Submits a diagnostic case, runs the deterministic engine, and atomically persists the case, observations, and initial revision-1 diagnosis to PostgreSQL, returning `201 Created`.
  - `GET /api/v1/cases/{case_id}` — Retrieves the persisted state of a case and its immutable revision-1 diagnosis by case UUID without recalculating diagnosis.
  - `POST /api/v1/cases/{case_id}/answers` — Submits a technician answer for an active case, executes Member 2's question-answer workflow, evaluates the next immutable analysis revision, and atomically persists the answer, derived observations, and revision N+1 snapshot to PostgreSQL.
  - `POST /api/v1/cases/{case_id}/check-results` — Submits a technician troubleshooting check result, executes Member 2's check workflow, evaluates the next immutable analysis revision, and atomically persists the check-result history, derived observations, and revision N+1 snapshot to PostgreSQL.
  - `POST /api/v1/cases/{case_id}/cause-confirmations` — Submits an explicit technician root-cause confirmation, executes Member 2's `confirm_cause()` diagnostic engine workflow, evaluates the next immutable analysis revision, and atomically persists the confirmation history and revision N+1 snapshot to PostgreSQL.
- **Contract & Scope:**
  - Requires active PostgreSQL database connection.
  - Uses `CaseRepository` to guarantee atomic writes and consistent reads.
  - GET endpoint performs zero recalculation and does not mutate case revisions.
  - Enforces optimistic concurrency via `expected_revision`, returning `409 Conflict` on stale submissions.
  - Rejects unknown question IDs, unsupported checks, and invalid cause IDs with `422 Unprocessable Entity`.
  - Preserves strict semantic independence: check completed != check supports cause != cause confirmed != issue resolved.
  - Returns `404 Not Found` for unknown case UUIDs and `422 Unprocessable Entity` for malformed IDs.
- **Full Specification:** See [API Specification](../docs/api/api-spec.md) for full schemas and execution payloads.
