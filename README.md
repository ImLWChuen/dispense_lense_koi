# DispenseIQ (DispenseLens)

**DispenseIQ** is an AI-assisted industrial dispensing defect diagnosis and troubleshooting platform. It provides technician decision support for manufacturing lines by structuring defect investigation across three distinct layers:

1. **Result Inspection:** Computer-vision measurement and classification of dispensing defects (e.g. undersized/oversized deposits, abnormal shape, coverage ratio, overflow ratio) under calibrated conditions.
2. **Process Context:** Equipment parameters, fluid material properties, valve and nozzle configurations, dispensing pressure, and ambient environmental conditions.
3. **Diagnostic Decision:** Deterministic cause ranking with numeric confidence percentages, actionable question/check recommendations, immutable analysis revisions, and independent root-cause confirmation and recovery tracking.

---

## Prerequisites

Ensure the following prerequisites are installed on your Windows development machine:

- **Windows PowerShell 5.1+** or **PowerShell 7+**
- **Docker Desktop** with the **Linux container engine** enabled and running
- **Python 3.11+** (tested up to Python 3.14 on Windows)
- **Node.js 18+** and **npm**

---

## First-Time Setup

Run the following commands from the repository root:

### 1. Copy Local Environment Configuration
Copy the template environment configuration to `.env` (this file is gitignored; do NOT commit secrets or real keys):
```powershell
Copy-Item .env.example .env
```

### 2. Backend Virtual Environment Setup
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
cd ..
```

### 3. Frontend Dependency Installation
```powershell
cd frontend
npm install
cd ..
```

---

## Repeatable Demo Startup Sequence

Follow these steps in order to start the platform for a local demonstration or rehearsal:

### Step 1: Run Preflight Check
Run the read-only preflight script to verify dependencies, compose validity, and port availability:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo-preflight.ps1
```
*If a required port (8000 or 3001) is occupied, the script identifies the occupying PID/process so you can stop it. Preflight never terminates external processes automatically.*

### Step 2: Start PostgreSQL Database
Start the persistent PostgreSQL 16 Compose container and wait for the health check to pass:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-db.ps1
```
*This starts the `dispenselens-postgres` container on port 5432 and preserves existing data in the `postgres_data` volume.*

### Step 3: Apply Database Migrations
Apply Alembic migrations to the development database (`dispenselens`):
```powershell
cd backend
$env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"
.\.venv\Scripts\python.exe -m alembic upgrade heads
cd ..
```

### Step 4: Start Backend API (Terminal 1)
Start the FastAPI application on port 8000:
```powershell
cd backend
$env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- API Base: `http://127.0.0.1:8000`
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`

### Step 5: Start Frontend Application (Terminal 2)
In a second terminal, start the Next.js development server on port **3001**:
```powershell
cd frontend
npm run dev -- -p 3001
```

> **IMPORTANT PORT WARNING:**
> The agreed demo port for DispenseIQ is **3001**.
> **Do NOT use port 3000.** Port 3000 may be occupied by unrelated local applications (e.g. Open-WebUI) or conflicting development servers. Always navigate to `http://localhost:3001`.

### Step 6: Verify Service Identity (Terminal 3)
In a third terminal, run the post-startup identity check:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-demo.ps1
```
This script confirms:
- `http://127.0.0.1:8000/api/v1/health` responds with `service="dispense-lens-api"`.
- `http://localhost:3001` responds with HTTP 200 and matches the DispenseIQ/DispenseLens application identity.
- Any conflicting service on those ports is rejected as the wrong local application.

### Step 7: Access the Prototype
Open your web browser and navigate to:
```
http://localhost:3001
```

---

## Safe Shutdown

When finishing a demonstration or development session:

1. Press `Ctrl+C` in the backend terminal window to stop the FastAPI process.
2. Press `Ctrl+C` in the frontend terminal window to stop the Next.js process.
3. Stop the PostgreSQL container without destroying data:
   ```powershell
   docker compose stop postgres
   ```
   *(Do NOT run `docker compose down -v`, as this deletes the development volume and purges existing demo cases).*

---

## Service Health vs. System Readiness

The backend health endpoint at `GET /api/v1/health` returns:
```json
{
  "status": "ok",
  "service": "dispense-lens-api",
  "version": "0.1.0"
}
```

### Health Scope & Deterministic Offline Operation
- `/api/v1/health` verifies **solely** that the FastAPI web service process is active, initialized, and handling HTTP requests.
- It **does not** verify database connectivity, CV inference pipelines, or external AI services.
- **Offline / Deterministic Diagnostic Authority:** The diagnostic engine runs **100% offline and deterministic** without an OpenAI API key. All cause ranking, numeric confidence calculations, and follow-up troubleshooting checks are driven by Member 2's deterministic rules and weights.
- **Optional LLM Summaries:** An `OPENAI_API_KEY` is completely optional. If configured, it generates narrative explanation summaries (`source="llm"`). If unconfigured or unavailable, the system transparently falls back to structured deterministic summaries (`source="deterministic"`). LLM output never mutates diagnosis scores, rankings, or case states.

---

## Troubleshooting

| Issue | Root Cause | Action / Resolution |
| :--- | :--- | :--- |
| `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified` | Docker Desktop is stopped or its Linux container engine is still initializing. | Open Docker Desktop from the Start menu and wait until the whale icon in the taskbar turns solid green. Then retry `scripts/start-db.ps1`. |
| `Port 8000 OCCUPIED by PID ...` | Another Python or backend process is listening on port 8000. | Use Task Manager or `Stop-Process -Id <PID>` to terminate the occupying process, or check `scripts/demo-preflight.ps1`. |
| `Port 3001 OCCUPIED by PID ...` | Another Node process is using port 3001. | Stop the old process before running `npm run dev -- -p 3001`. |
| Browser shows Open-WebUI or wrong interface | Navigated to `http://localhost:3000` instead of `3001`. | Port 3000 is reserved for external tools. Navigate explicitly to `http://localhost:3001`. |
| `Backend Python: Not found` | Virtual environment was not created. | In `backend/`, run `python -m venv .venv` and `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`. |
| `Frontend dependencies: Missing` | Node packages are uninstalled. | In `frontend/`, run `npm install`. |
| `DATABASE_URL: Not configured` | Environment variable is unset in session. | Set `$env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"` in PowerShell. |
| Alembic migration fails | PostgreSQL container is not running or unhealthy. | Run `scripts/start-db.ps1` to ensure `dispenselens-postgres` is healthy before migrating. |

---

## Further Documentation

- [Competition Demo Runbook](docs/demo/local-demo-runbook.md): Timed 6–10 minute operator walkthrough, narrative script, failure fallbacks, and rehearsal logs.
- [Backend Documentation](backend/README.md): Detailed database test safety policy, Alembic commands, and backend test suites.
- [API Specification](docs/api/api-spec.md): Complete request/response schemas for stateless diagnoses and durable lifecycle endpoints.
