# DispenseIQ (DispenseLens)

**DispenseIQ** is an AI-assisted industrial dispensing defect diagnosis and troubleshooting platform. It provides technician and engineering decision support for manufacturing lines by structuring defect investigation across three distinct layers:

1. **Result Inspection:** Computer-vision measurement and classification of dispensing defects (e.g., undersized/oversized deposits, abnormal shape, interior void/bubbles, coverage ratio, overflow ratio) under calibrated optics.
2. **Process Context:** Equipment parameters, fluid material properties, valve and nozzle configurations, dispensing pressure, syringe pot-life, and ambient cleanroom environmental conditions.
3. **Diagnostic Decision:** Deterministic cause ranking with cumulative evidence support scores (`Evidence Support /100`), actionable question/check recommendations, immutable analysis revisions, and independent root-cause confirmation and recovery tracking.

---

## System Requirements & Prerequisites

Ensure the following prerequisites are installed on your workstation:

- **Operating System:** Windows 10/11 (with **PowerShell 5.1+** or **PowerShell 7+**)
- **Docker Desktop:** Running with the **Linux container engine** enabled (used for PostgreSQL 16)
- **Python:** **Python 3.11+** (tested up to Python 3.14 on Windows; `uv` or standard `python -m venv`)
- **Node.js:** **Node.js 20.9.0+** (v20 or v22 LTS recommended for Next.js 16) and **npm**

---

## First-Time Setup

Run the following commands from the repository root (`c:\dispense_lense_koi`):

### 1. Configure Environment Files

Create backend and frontend environment configurations from the provided examples:

```powershell
# Root / Backend environment template
Copy-Item .env.example .env
Copy-Item .env.example backend\.env
```

Ensure `backend/.env` contains the local database connection:
```ini
DATABASE_URL=postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,http://localhost:8000,http://127.0.0.1:8000
```

Ensure `frontend/.env.local` is configured with the explicit IPv4 address to eliminate 2-second Windows IPv6 dual-stack timeouts:
```ini
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1
```

### 2. Backend Virtual Environment Setup

Using `uv` (recommended):
```powershell
cd backend
uv sync
cd ..
```

*Or using standard Python:*
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

## Step-by-Step System Startup Sequence

Follow these steps in order to start the platform for a local demonstration or development session:

```
+--------------------------+       +--------------------------+       +--------------------------+
|  1. Preflight Check      |  -->  |  2. Start PostgreSQL     |  -->  |  3. Run DB Migrations    |
|  scripts/demo-preflight  |       |  scripts/start-db.ps1    |       |  alembic upgrade heads   |
+--------------------------+       +--------------------------+       +--------------------------+
                                                                                    |
                                                                                    v
+--------------------------+       +--------------------------+       +--------------------------+
|  6. Verify System        |  <--  |  5. Start Frontend       |  <--  |  4. Start Backend API    |
|  scripts/verify-demo.ps1 |       |  Port 3001 (Next.js)     |       |  Port 8000 (FastAPI)     |
+--------------------------+       +--------------------------+       +--------------------------+
            |
            v
   http://localhost:3001
```

### Step 1: Run Preflight Check
Run the read-only preflight diagnostic to verify toolchains, Docker status, and port availability:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo-preflight.ps1
```
> *If a required port (8000 or 3001) is occupied by an existing process, the script identifies the occupying PID so you can stop it before proceeding.*

### Step 2: Start PostgreSQL Database
Start the persistent PostgreSQL 16 container and wait for its health check to pass:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-db.ps1
```
*This starts the `dispenselens-postgres` container on port `5432` and safely preserves existing test data in the `postgres_data` volume.*

### Step 3: Run Database Migrations
Apply Alembic migrations to ensure the database schema is up-to-date:
```powershell
cd backend
$env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"
.\.venv\Scripts\python.exe -m alembic upgrade heads
cd ..
```
*(If using `uv`: `uv run alembic upgrade heads`)*

### Step 4: Start Backend API (Terminal 1)
Start the FastAPI server on port `8000`:
```powershell
cd backend
$env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
*(If using `uv`: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`)*

- **API Base:** `http://127.0.0.1:8000`
- **Health Check:** `http://127.0.0.1:8000/api/v1/health`
- **OpenAPI Interactive Docs:** `http://127.0.0.1:8000/docs`

### Step 5: Start Frontend Application (Terminal 2)
In a separate terminal, launch the Next.js frontend dev server on the **agreed demo port (3001)**:
```powershell
cd frontend
npm run dev -- -p 3001
```

> [!WARNING]
> **CRITICAL PORT REQUIREMENT:**
> The agreed demo port for DispenseIQ is **3001** (`http://localhost:3001`).
> **Do NOT use port 3000.** Port 3000 is often claimed by other background software (such as Open-WebUI) and is outside the project's verification contract.

### Step 6: Verify Service Identity (Terminal 3)
Run the automated post-start identity check to confirm both services are responding with the expected DispenseLens signature:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-demo.ps1
```

Expected output:
```text
[PASS] Backend Identity Verified:
       Service: dispense-lens-api
       Status:  ok
       Version: 0.1.0

[PASS] Frontend Identity Verified: Responding at http://localhost:3001 (HTTP 200)
       Page identity: Matches DispenseLens / DispenseIQ application.
```

### Step 7: Open the Application
Open your browser and navigate to:
```
http://localhost:3001
```

---

## Default Demo Credentials

On the login screen (`http://localhost:3001/login`), you can use the one-click credential buttons or enter any of the following accounts:

| Role | Email | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **Engineer (Default)** | `sarah.mitchell@example.com` | `password123` | Full diagnosis intake, 8D report generation, cause confirmations |
| **Technician** | `tech@example.com` | `password` | Shopfloor intake, checklist execution, live telemetry monitoring |
| **Administrator** | `admin@example.com` | `password` | User role management, line thresholds, audit access (`/admin`) |

---

## Workstation Appearance & Interface Density

DispenseIQ includes cleanroom-optimized visual display profiles tailored for microscope screens and touch terminals:

1. Navigate to **Settings** (`/settings`) from the left sidebar.
2. Select the **Appearance & Theme** tab:
   - **Cleanroom Day:** High-contrast light interface optimized for brightly lit cleanrooms.
   - **Low-Glare Night:** Deep obsidian palette (`#0b0f19`) reducing eye fatigue under microscope magnification.
   - **System Sync:** Automatically synchronizes with the host operating system's dark/light preference.
   - **Interface Density:** Switch between **Comfortable (Default)** and **Compact Cleanroom** (tightened paddings and compact data tables for 1080p touch panels).
3. Preferences persist across browser sessions and apply immediately without layout flashing.

---

## Safe Shutdown Protocol

When concluding a session or demonstration:

1. Press `Ctrl + C` in **Terminal 1** (Backend FastAPI).
2. Press `Ctrl + C` in **Terminal 2** (Frontend Next.js).
3. Gracefully stop the PostgreSQL container while keeping the database volume intact:
   ```powershell
   docker compose stop postgres
   ```

> [!CAUTION]
> **DO NOT** execute `docker compose down -v`. The `-v` flag removes the Docker named volume (`postgres_data`), wiping all persisted cases, checklists, and 8D reports.

---

## Deterministic Offline Architecture vs. Optional LLM

- **100% Offline & Deterministic Diagnostic Engine:** The diagnostic decision engine, cause rankings, dynamic question discrimination, and physical checklist recommendations run completely offline with mathematical determinism. No external API key is needed.
- **Optional Narrative AI Summaries:** If an `OPENAI_API_KEY` is configured in `backend/.env`, the system generates bounded narrative explanations (`source="llm"`). If unconfigured, timed out, or unavailable, it transparently falls back to deterministic structured summaries (`source="deterministic"`). The LLM never modifies scores, rankings, or case states.

---

## Troubleshooting Guide

| Symptom / Error | Root Cause | Recommended Action |
| :--- | :--- | :--- |
| `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified` | Docker Desktop is not running or the Linux VM is still starting. | Start Docker Desktop from the Windows Start menu and wait until the whale icon shows "Engine running". Then re-run `.\scripts\start-db.ps1`. |
| `Port 8000 OCCUPIED by PID ...` | A background Python/Uvicorn process is holding port 8000. | Stop the process via Task Manager or PowerShell: `Stop-Process -Id <PID> -Force`. |
| `Port 3001 OCCUPIED by PID ...` | A previously started Next.js dev server is still listening on port 3001. | Stop the process using `Stop-Process -Id <PID> -Force` before running `npm run dev -- -p 3001`. |
| Browser opens Open-WebUI or unknown service | Accidentally browsed to port 3000 instead of 3001. | Always access `http://localhost:3001`. Port 3000 is not used by DispenseIQ. |
| Page navigation takes ~2 seconds on Windows | Dual-stack localhost lookup delay (`localhost` resolving to IPv6 `::1` before falling back). | Ensure `frontend/.env.local` contains `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1`. |
| `DATABASE_URL: Not configured` | Environment variable not passed into the active PowerShell session. | Set `$env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"`. |
| `Backend Python: Not found` | Virtual environment was not created. | In `backend/`, run `uv sync` or `python -m venv .venv` and install `.[dev]`. |
| `Alembic upgrade: connection refused` | PostgreSQL container is not started. | Run `powershell -ExecutionPolicy Bypass -File .\scripts\start-db.ps1` and verify port 5432 is listening. |

---

## Verification & Automated Test Suites

To verify changes after pulling or making modifications:

```powershell
# 1. Backend Unit Tests (255 tests)
cd backend
uv run pytest tests/unit/
cd ..

# 2. Frontend Typecheck
cd frontend
npx tsc --noEmit
cd ..

# 3. Frontend Workflow & State Suites
node frontend/scripts/test-case-detail-state.mjs
node frontend/scripts/test-diagnostic-workflow-state.mjs
node frontend/scripts/test-image-upload-state.mjs
node frontend/scripts/test-reports-state.mjs
node frontend/scripts/test-knowledge-catalog-state.mjs

# 4. End-to-End Service Identity Verification
powershell -ExecutionPolicy Bypass -File .\scripts\verify-demo.ps1
```

---

## Further Documentation

- [Demo Runbook](docs/demo/local-demo-runbook.md): Timed 6–10 minute demonstration sequence, stage script, and operator talk tracks.
- [API Specification](docs/api/api-spec.md): Schema definitions for stateless diagnostics, image uploads, and case lifecycle endpoints.
- [Dynamic Question Discrimination Pitch](docs/competition/pitch-dynamic-question-discrimination.md): Mathematical information-gain model and dynamic troubleshooting tree documentation.
