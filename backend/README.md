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

## Running Tests

Run the test suite using pytest:

```powershell
# Run the focused health API test
.\.venv\Scripts\python.exe -m pytest tests/integration/test_health_api.py -q

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
