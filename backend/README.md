# Dispense Lens Backend

Backend service for the Dispense Lens competition prototype, built with FastAPI.

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

3. Synchronize declared runtime and development dependencies:
   ```powershell
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   ```

4. Verify dependency consistency:
   ```powershell
   .\.venv\Scripts\python.exe -m pip check
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

### 2. Configure Environment Variables

Set environment variables in your shell (or copy `.env.example` to `.env` for local work; do NOT commit `.env`):

```powershell
# Development database URL (for runtime application server and dev data)
$env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"

# Disposable test database URL (for automated pytest integration suites)
$env:TEST_DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test"

# Optional: Bounded LLM Configuration (defaults to offline deterministic fallback if unset)
# $env:OPENAI_API_KEY = "your-api-key"
# $env:OPENAI_MODEL = "gpt-4o-mini"
```

> **Note on Test Safety Policy:**
> Automated database-backed tests enforce strict fail-closed destination validation via `TEST_DATABASE_URL`. Connections must target approved local test hosts (`localhost`, `127.0.0.1`, `::1`, `dispenselens-postgres`, `postgres`) and disposable test database names (`dispenselens_test`, `test`, `test_*`, `*_test`).
>
> Testing against the plain development database name (`dispenselens`) or pointing `TEST_DATABASE_URL` to the same database as `DATABASE_URL` is strictly rejected to protect development data. Connection query parameters that override destination parameters are also rejected.

### 3. Create Disposable Test Database (Non-Destructive)

Create the `dispenselens_test` database if it does not already exist:
```powershell
docker exec -i dispenselens-postgres psql -U dispenselens_user -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'dispenselens_test'"
# If empty / not found, create it:
docker exec -i dispenselens-postgres psql -U dispenselens_user -d postgres -c "CREATE DATABASE dispenselens_test;"
```

### 4. Apply Migrations to Disposable Test Database

Before running tests, ensure the disposable test database is migrated to `head`.
Validate the test URL before Alembic, save the original `DATABASE_URL`, temporarily bind the test URL inside `try/finally`, and restore its original value or absence before pytest:

```powershell
# Ensure TEST_DATABASE_URL is set
$env:TEST_DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test"

# Validate test database destination safety and development separation prior to Alembic execution
$origDb = $env:DATABASE_URL
.\.venv\Scripts\python.exe -c "from tests.unit.test_persistence_safety import assert_safe_test_database; import os; assert_safe_test_database(os.environ.get('TEST_DATABASE_URL', ''), dev_url=os.environ.get('DATABASE_URL'))"
if ($LASTEXITCODE -ne 0) {
    throw "Test database safety validation failed (exit code $LASTEXITCODE). Migration aborted."
}

# Temporarily present TEST_DATABASE_URL to Alembic and restore original environment upon completion
try {
    $env:DATABASE_URL = $env:TEST_DATABASE_URL
    .\.venv\Scripts\python.exe -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Alembic migration failed (exit code $LASTEXITCODE)."
    }
} finally {
    if ($null -ne $origDb) { $env:DATABASE_URL = $origDb } else { Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue }
}
```

> **Optional: Development Database Migrations**
> If you are setting up or upgrading the development database (`dispenselens`) for manual runtime usage, run:
> ```powershell
> $env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"
> .\.venv\Scripts\python.exe -m alembic upgrade head
> ```

## Running Tests

Automated tests require `TEST_DATABASE_URL` for database-backed suites. The centralized test bootstrap validates destination safety and separation from `DATABASE_URL` before binding within the pytest runner. Unit and health tests run independently without requiring a database connection or `TEST_DATABASE_URL`.

```powershell
# Ensure test database target is set in PowerShell session:
$env:TEST_DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test"

# If DATABASE_URL is set in your shell for development, ensure it targets the development database (not the test database):
$env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"

# Run non-database checks (health endpoint, test safety, runtime baseline)
.\.venv\Scripts\python.exe -m pytest tests/integration/test_health_api.py -q
.\.venv\Scripts\python.exe -m pytest tests/unit/test_persistence_safety.py -q
.\.venv\Scripts\python.exe -m pytest tests/unit/test_runtime_baseline.py -q
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ai_outputs.py -q
.\.venv\Scripts\python.exe -m pytest tests/unit/test_teammate_integration_contracts.py -q

# Run focused PostgreSQL persistence integration tests (uses TEST_DATABASE_URL)
.\.venv\Scripts\python.exe -m pytest tests/integration/test_persistence.py -q
.\.venv\Scripts\python.exe -m pytest tests/integration/test_mvp_backend_acceptance.py -q

# Run all backend tests
.\.venv\Scripts\python.exe -m pytest -q
```

## Running the Development Server

Start the local FastAPI development server on port 8000:

```powershell
# Restore development database URL for runtime execution:
$env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Backend runs at: `http://127.0.0.1:8000`
- Configured CORS origins include `http://localhost:3001` and `http://127.0.0.1:3001` for the Next.js frontend (as well as `http://localhost:3000` / `http://127.0.0.1:3000`).
- Interactive OpenAPI documentation:
  - Swagger UI: `http://127.0.0.1:8000/docs`
  - OpenAPI JSON specification: `http://127.0.0.1:8000/openapi.json`
- Offline / Deterministic Troubleshooting:
  - When `OPENAI_API_KEY` (or `LLM_API_KEY`) is not set, the backend runs completely offline with deterministic ranking, scoring, and explanation fallbacks. No OpenAI client or outbound network calls are made.

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
  - `POST /api/v1/cases` - Submits a diagnostic case, runs the deterministic engine, and atomically persists the case, observations, and initial revision-1 diagnosis to PostgreSQL, returning `201 Created`.
  - `GET /api/v1/cases/{case_id}` - Retrieves the persisted state of a case and its immutable revision-1 diagnosis by case UUID without recalculating diagnosis.
  - `POST /api/v1/cases/{case_id}/answers` - Submits a technician answer for an active case, executes Member 2's question-answer workflow, evaluates the next immutable analysis revision, and atomically persists the answer, derived observations, and revision N+1 snapshot to PostgreSQL.
  - `POST /api/v1/cases/{case_id}/check-results` - Submits a technician troubleshooting check result, executes Member 2's check workflow, evaluates the next immutable analysis revision, and atomically persists the check-result history, derived observations, and revision N+1 snapshot to PostgreSQL.
  - `POST /api/v1/cases/{case_id}/cause-confirmations` - Submits an explicit technician root-cause confirmation, executes Member 2's `confirm_cause()` diagnostic engine workflow, evaluates the next immutable analysis revision, and atomically persists the confirmation history and revision N+1 snapshot to PostgreSQL.
- **Contract & Scope:**
  - Requires active PostgreSQL database connection.
  - Uses `CaseRepository` to guarantee atomic writes and consistent reads.
  - GET endpoint performs zero recalculation and does not mutate case revisions.
  - Enforces optimistic concurrency via `expected_revision`, returning `409 Conflict` on stale submissions.
  - Rejects unknown question IDs, unsupported checks, and invalid cause IDs with `422 Unprocessable Entity`.
  - Preserves strict semantic independence: check completed != check supports cause != cause confirmed != issue resolved.
  - Returns `404 Not Found` for unknown case UUIDs and `422 Unprocessable Entity` for malformed IDs.
- **Full Specification:** See [API Specification](../docs/api/api-spec.md) for full schemas and execution payloads.
