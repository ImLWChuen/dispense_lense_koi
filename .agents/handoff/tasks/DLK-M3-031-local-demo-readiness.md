---
task_id: DLK-M3-031
title: Repeatable local demo startup and operator runbook
status: implemented
created_by: ChatGPT planner/reviewer
assigned_to: Gemini 3.8 Flash implementer
depends_on: [DLK-M3-030]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-031: Repeatable local demo startup and operator runbook

## Objective

Make the accepted DispenseIQ prototype reliably runnable by a teammate on Windows PowerShell without changing product behavior.

The observable outcome is a release package that:

1. starts the existing PostgreSQL Compose service without a developer-specific Docker path;
2. detects missing Docker, a stopped Docker engine, missing local dependencies, and occupied application ports with clear corrective messages;
3. documents the exact backend and frontend startup sequence on ports `8000` and `3001`;
4. proves that the services at those ports are the DispenseLens API and DispenseIQ frontend rather than another local application;
5. provides a timed, truthful competition-demo and recovery runbook.

This is the next dependency because DLK-M3-030 accepted the application behavior, but the current root documentation and database helper can still direct a teammate to the wrong application or fail on another Windows account.

## Current evidence

- DLK-M3-030 is accepted at commit `747235695fa9777a8b9f84f4b47e66844b50a98f` with 491 backend tests passing, all focused frontend state scripts passing, frontend lint clean, and the production build successful.
- `.agents/handoff/reviews/DLK-M3-030-review.md` records the accepted review and is intentionally pending inclusion in this next atomic task commit.
- The repository root `README.md` is still the default Create Next App text. It says to run `npm run dev` from the repository root and open `http://localhost:3000`, neither of which is the agreed project startup path.
- The frontend package is under `frontend/`, and its API client defaults to `http://localhost:8000/api/v1`.
- The agreed frontend demo port is `3001`; `.env.example` and backend CORS defaults already include it.
- Port `3000` can contain an unrelated local OpenUI service, so the project must not direct the operator there.
- `scripts/start-db.ps1` currently hardcodes `C:\Users\koay\AppData\Local\Programs\DockerDesktop\resources\bin`, then calls Compose without checking whether the Docker CLI or engine is available.
- The known Docker failure `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified` means the Docker Desktop Linux engine is unavailable, not that the PostgreSQL image or DispenseIQ application is defective.
- `compose.yaml` defines a persistent PostgreSQL 16 service named `postgres`, container `dispenselens-postgres`, with a health check and a named volume `postgres_data`.
- `backend/README.md` contains accurate but fragmented backend setup commands. The root README must become the authoritative short path and link to the backend document for detailed test setup.
- There is no repository-level demo preflight, application identity check, or competition rehearsal runbook.
- Product behavior, API contracts, database schema, diagnostic semantics, and UI flows were accepted in DLK-M3-030 and are not open for redesign here.

## Requirements

### 1. Make PostgreSQL startup portable and fail clearly

Refactor `scripts/start-db.ps1` so it:

- resolves the repository root from `$PSScriptRoot` and works regardless of the caller's current directory;
- finds Docker through `Get-Command docker` rather than a user-specific installation path;
- distinguishes at least these failures with concise actionable output and a non-zero exit:
  - Docker CLI is not installed or is not on `PATH`;
  - Docker CLI exists but the Docker engine is not running/available;
  - Compose configuration is invalid;
  - Compose cannot start the `postgres` service;
  - the PostgreSQL container does not become healthy within a bounded wait;
- runs Compose against this repository's `compose.yaml` and starts only `postgres`;
- waits for the existing Compose health check to report healthy before returning success;
- preserves the named development volume and all existing development records;
- never runs `docker compose down -v`, deletes volumes, resets a database, or creates a replacement database silently;
- never prints credentials or complete database URLs.

The engine-unavailable message must explicitly tell the operator to start Docker Desktop and wait until its Linux engine is running before retrying.

### 2. Add a read-only demo preflight

Add `scripts/demo-preflight.ps1` for Windows PowerShell. It must be safe to run repeatedly and make no persistent changes.

It must check and report, without printing secrets:

- Docker CLI and engine availability;
- valid repository Compose configuration;
- repository-local backend interpreter at `backend/.venv/Scripts/python.exe`;
- Node.js and npm availability;
- installed frontend dependencies required to run the checked-in Next.js version;
- whether `DATABASE_URL` is configured either in the current environment or an applicable repository/backend `.env` file, reporting only presence/absence;
- whether ports `8000` and `3001` are available before startup.

If a required port is occupied, preflight must fail, identify the local PID/process when Windows exposes it, and tell the operator to stop or reconfigure that service. It must never terminate another process automatically. Port `3000` is outside the project startup contract and must not be substituted automatically.

Every failed required check must produce a non-zero exit. A successful preflight must state the next exact command to run.

### 3. Add a post-start application identity check

Add `scripts/verify-demo.ps1`. It must be read-only, return a non-zero exit on failure, use bounded HTTP timeouts, and verify:

- `GET http://127.0.0.1:8000/api/v1/health` returns the existing API identity (`status: ok`, `service: dispense-lens-api`);
- `http://localhost:3001` responds as the DispenseIQ/DispenseLens frontend using stable checked-in page identity such as the document title or rendered product name;
- an HTTP service that responds but does not have the expected identity is reported as the wrong local application, not as a successful DispenseIQ startup.

Do not add a new health endpoint or change frontend production code solely to satisfy this script. Use existing stable identity already rendered or emitted by the application.

### 4. Replace the root README with an accurate project quickstart

Rewrite `README.md` for DispenseIQ. Keep it concise but complete enough for a teammate starting from a fresh clone on Windows PowerShell.

It must include:

- what the prototype does and the three-layer flow: result inspection, process context, diagnostic decision;
- prerequisites: Docker Desktop with Linux containers, Python 3.11+, Node.js/npm, and PowerShell;
- first-time dependency setup for `backend/.venv` and `frontend/node_modules`;
- copying `.env.example` to local `.env` without committing it;
- the exact sequence:
  1. `scripts/demo-preflight.ps1`;
  2. `scripts/start-db.ps1`;
  3. development migration with `DATABASE_URL` targeting `dispenselens`;
  4. backend on `127.0.0.1:8000` from `backend/`;
  5. frontend on explicit port `3001` from `frontend/`;
  6. `scripts/verify-demo.ps1`;
  7. open `http://localhost:3001`;
- a warning that `http://localhost:3000` is not the project URL for this demo configuration;
- safe shutdown: stop both development processes with `Ctrl+C`, then stop only the Compose PostgreSQL service without deleting its volume;
- troubleshooting for the Docker engine pipe error, occupied ports/wrong local UI, missing virtual environment, missing `node_modules`, missing `DATABASE_URL`, and a failed migration;
- links to `backend/README.md`, API docs, and the new demo runbook for deeper detail.

Do not include a real API key, claim that OpenAI is required, or imply that the health endpoint proves database/AI/CV readiness. State that the deterministic diagnostic path works without an OpenAI key.

### 5. Add the competition demo and recovery runbook

Add `docs/demo/local-demo-runbook.md` with:

- a pre-demo checklist that uses the new scripts and verifies a development database, not the disposable automated-test database;
- a 6–10 minute timed walkthrough of the existing product:
  - frame the technician problem and evidence-based ranking;
  - create a real durable case from process context and symptom evidence;
  - optionally add calibrated image evidence under the accepted image limitations;
  - show ranked causes with numeric confidence and short supporting/contradicting evidence;
  - answer one follow-up question or record one check and show the ranking revision;
  - explicitly confirm a cause;
  - record a recovery action;
  - verify recovery separately from cause confirmation;
  - show durable case history plus report/PDF/dashboard evidence;
- exact truthful claims and limitations:
  - decision support for new technicians, not autonomous machine control;
  - deterministic evidence ranking remains authoritative;
  - LLM summaries are optional explanations and do not change scores/state;
  - no live dispensing-machine integration or production accuracy claim;
  - image evidence is limited to documented calibrated/controlled conditions;
  - vector similarity, authentication, and deferred hardware integrations are not part of the prototype;
- a fallback plan for each demo dependency: Docker/PostgreSQL, backend, frontend, image input, and optional OpenAI summary;
- a reset-free rehearsal policy: preserve useful development records, use clearly synthetic demonstration inputs, and never run automated tests against the development database;
- a short three-run rehearsal checklist with operator, narrator, expected outcome, elapsed time, and observed issue fields.

The runbook may prescribe synthetic demo inputs, but it must label them as synthetic and must not include private customer data or arbitrary unlicensed internet images.

### 6. Preserve accepted application behavior

- Do not change backend or frontend product code unless an actual release-blocking startup defect is reproduced and returned to the planner first.
- Do not change API contracts, schema/migrations, diagnostic rules, score meaning, question/check semantics, image-analysis meaning, or lifecycle state transitions.
- Do not add dependencies or a new test framework.
- Do not run destructive database or Docker volume commands.

## Interfaces and data contracts

No application API, persistence, schema, or diagnostic contract changes are authorized.

Operational interfaces introduced by this task:

- `scripts/start-db.ps1`
  - input: current local Docker installation/engine and repository `compose.yaml`;
  - output: healthy existing `postgres` Compose service or a non-zero actionable failure;
  - persistence: may start the existing persistent container/volume; must not modify application rows directly.
- `scripts/demo-preflight.ps1`
  - input: local tool/dependency/environment/port state;
  - output: human-readable pass/fail report and process exit code;
  - persistence: none.
- `scripts/verify-demo.ps1`
  - input: running services on ports `8000` and `3001`;
  - output: verified DispenseLens/DispenseIQ identity or a non-zero failure;
  - persistence: none; HTTP checks must be GET-only.

All scripts must avoid echoing environment values that may contain credentials.

## Allowed paths

- `README.md`
- `scripts/start-db.ps1`
- `scripts/demo-preflight.ps1`
- `scripts/verify-demo.ps1`
- `docs/demo/local-demo-runbook.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/tasks/DLK-M3-031-local-demo-readiness.md`
- `.agents/handoff/reviews/DLK-M3-030-review.md` (include the already accepted pending record unchanged)

## Prohibited scope

- Backend/frontend product behavior changes without first returning a reproduced release blocker to the planner.
- API, database, migration, diagnostic-engine, scoring, AI/CV, lifecycle, or authentication changes.
- New dependencies, test frameworks, containers, deployment platforms, CI/CD redesign, or production hosting.
- Implementing vector similarity, hardware/machine integration, new AI/CV models, or D06 score-bearing vision semantics.
- Committing `.env`, secrets, keys, credentials, uploaded images, database dumps, logs, dependencies, or generated build output.
- Touching unrelated untracked files, including `.agents.zip`, `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md`, `frontend/AGENTS.md`, or `frontend/CLAUDE.md`.
- Killing processes automatically, resetting databases, deleting Docker volumes, or running tests against the development database.
- Remote Git operations and changes to `main`.

## Implementation guidance

1. Inspect the current scripts, Compose service, health response, frontend metadata, and current README before editing.
2. Implement small PowerShell helper functions where they reduce duplicated error handling, but keep the scripts understandable to undergraduate maintainers.
3. Resolve paths from `$PSScriptRoot`; do not depend on the current shell directory or any username-specific path.
4. Prefer fail-closed checks and bounded waits. Preserve original command exit codes where practical.
5. Keep preflight read-only. Let `start-db.ps1` own the authorized Compose startup mutation.
6. Use only GET requests in `verify-demo.ps1` and assert identity, not merely HTTP 200.
7. Write README and runbook commands for PowerShell. Use single-line commands or PowerShell backticks, never Bash `\` continuation.
8. Run the scripts through the documented real sequence when local prerequisites permit. If an external prerequisite is unavailable, exercise the deterministic failure branch and record the exact limitation honestly; do not weaken the acceptance behavior.
9. Update this task to `implemented` and `QUEUE.md` to `implemented` only after the required checks pass. Include the pending accepted DLK-M3-030 review record in the atomic local commit.

## Acceptance criteria

- [ ] `scripts/start-db.ps1` contains no developer-specific absolute path, works from outside the repository directory, and returns success only after the existing PostgreSQL service is healthy.
- [ ] Missing Docker CLI, unavailable Docker engine, invalid Compose configuration, failed service startup, and health timeout each return a non-zero result with distinct actionable text.
- [ ] The Docker engine pipe failure directs the operator to start Docker Desktop/Linux containers and retry.
- [ ] No script deletes/resets data, removes volumes, kills unrelated processes, or prints secrets/database URLs.
- [ ] `scripts/demo-preflight.ps1` is repeatable and read-only; it checks required tools, dependencies, database configuration presence, Compose validity, and ports `8000`/`3001`.
- [ ] An occupied required port fails preflight and reports available PID/process information without terminating it; port `3000` is never substituted.
- [ ] `scripts/verify-demo.ps1` accepts only the expected backend and frontend identities and rejects an unrelated HTTP service even when it returns 200.
- [ ] Root `README.md` contains a runnable Windows PowerShell setup/start/verify/stop sequence and consistently uses `http://localhost:3001` for the project UI.
- [ ] The root README accurately distinguishes API process health from database/AI/CV readiness and documents deterministic offline behavior.
- [ ] `docs/demo/local-demo-runbook.md` contains a truthful 6–10 minute flow, failure fallbacks, limitations, data-safety rules, and a three-run rehearsal checklist.
- [ ] No application code, dependency manifest, API contract, schema, scoring rule, or diagnostic knowledge changed.
- [ ] The existing frontend lint/build and focused backend health test still pass.
- [ ] Only allowed task paths are staged; unrelated untracked files remain untouched.

## Verification

Run from the repository root unless a step says otherwise:

1. Confirm all PowerShell scripts parse without syntax errors using `System.Management.Automation.Language.Parser.ParseFile`.
2. Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\demo-preflight.ps1` before application startup; verify either a complete pass or the correct non-zero actionable prerequisite failure.
3. Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-db.ps1`; verify `docker inspect --format "{{.State.Health.Status}}" dispenselens-postgres` reports `healthy` when Docker is available.
4. Apply the existing development migrations from `backend/` using the configured development `DATABASE_URL`: `.\.venv\Scripts\python.exe -m alembic upgrade head`.
5. Start the existing backend on `127.0.0.1:8000` and frontend on port `3001` using the exact README commands. Do not use port `3000`.
6. Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-demo.ps1` and record the verified backend/frontend identities.
7. Exercise at least one controlled wrong-service/unavailable-service path for `verify-demo.ps1` and confirm a non-zero exit without stopping any process.
8. From `backend/`: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_health_api.py -q`.
9. From `frontend/`: `npm run lint`.
10. From `frontend/`: `npm run build`.
11. From the repository root: `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-031-local-demo-readiness.md`.
12. From the repository root: `git diff --check` and `git status --short`.

Do not run the full database-backed automated test suite against the development database. If broader backend tests are run, use the separately configured disposable `TEST_DATABASE_URL` and retain the existing destination-safety checks.

## Planner decision boundaries

Return to the planner before changing product code, architecture, public interfaces, database contracts, dependencies, ownership boundaries, security requirements, diagnostic/evidence meaning, or task scope. Also return before choosing a new port, adding a process supervisor, containerizing the application services, or weakening a failed preflight/identity check.

If local Docker or another external prerequisite is unavailable, implement and verify the safe failure behavior, record the blocked live step, and return to the planner. Do not fabricate a successful live run.

## Git instructions

Create one atomic local commit after all required checks pass. Include:

- the completed DLK-M3-031 task packet and queue update;
- the already accepted pending `.agents/handoff/reviews/DLK-M3-030-review.md` record;
- only the allowed release-readiness files changed for this task.

Do not stage unrelated untracked files. Do not push, merge, rebase a shared branch, create/update a pull request, or change `main`.

Proposed commit message: `docs(demo): make local competition startup repeatable`

## Implementation report

### Summary

Delivered all local demo readiness and competition rehearsal requirements for DLK-M3-031:
1. Refactored `scripts/start-db.ps1`:
   - Made repository-path-independent using `$PSScriptRoot` (works regardless of caller directory).
   - Removed all user-specific and hardcoded paths (`C:\Users\koay\...`), finding Docker via `Get-Command docker`.
   - Distinguishes missing Docker CLI, engine-unavailable (directing operator to start Docker Desktop Linux engine), invalid Compose configuration, Compose startup errors, and container health check timeouts with concise actionable text and non-zero exit.
   - Preserved `postgres_data` volume and development database records without destructive commands (`down -v`, volume deletions, or silent replacements).
2. Created `scripts/demo-preflight.ps1`:
   - Safe, read-only Windows PowerShell script that validates Docker CLI, Docker engine, Compose configuration, local Python virtual environment (`backend\.venv\Scripts\python.exe`), Node.js/npm, frontend dependencies (`frontend\node_modules\next`), `DATABASE_URL` presence (reporting presence/absence only, never printing secret connection strings), and pre-startup port availability on ports `8000` and `3001`.
   - Rejects occupied ports with PID and process name identification without terminating external processes; reminds operator that port `3000` is outside the project startup contract.
   - States the exact next command (`scripts\start-db.ps1`) upon complete pass.
3. Created `scripts/verify-demo.ps1`:
   - Read-only post-startup verification script asserting backend identity on `http://127.0.0.1:8000/api/v1/health` (`service="dispense-lens-api"`, `status="ok"`) and frontend identity on `http://localhost:3001` (`<title>DispenseLens</title>` / DispenseIQ application content).
   - Rejects non-DispenseIQ services on those ports (such as Open-WebUI on port 3000) as wrong local applications with actionable failure messages.
4. Replaced root `README.md`:
   - Replaced Create Next App boilerplate with a comprehensive project quickstart covering the three-layer diagnostic flow, prerequisites, first-time dependency setup, development database migration (`alembic upgrade heads`), exact startup commands for backend (8000) and frontend (3001), health scope vs. readiness distinction, offline deterministic operation, port 3000 avoidance warning, safe shutdown, troubleshooting matrix, and documentation links.
5. Created `docs/demo/local-demo-runbook.md`:
   - Structured 6–10 minute timed competition demonstration script covering problem framing, context/case creation, calibrated image analysis evidence, deterministic cause ranking, troubleshooting checks, root-cause confirmation, recovery actions, and report/PDF export.
   - Detailed truthful claims and engineering limitations (technician decision support, deterministic scoring authority, optional LLM explanations, calibrated optical vision boundaries, deferred hardware integration).
   - Fallback procedures for each component (Docker, backend, frontend, camera/image, OpenAI) and a reset-free rehearsal record table.

### Files changed

Primary feature paths:
- `scripts/start-db.ps1`: Refactored to be path-independent, portable, distinguish engine failures, wait for container health, and preserve development volume.
- `scripts/demo-preflight.ps1`: Added read-only preflight check for Docker, Python, Node, npm, dependencies, config presence, and ports 8000/3001.
- `scripts/verify-demo.ps1`: Added post-startup identity verification asserting backend `dispense-lens-api` and frontend `DispenseLens`/`DispenseIQ` presence.
- `README.md`: Authoritative project quickstart, prerequisites, setup, startup sequence, port 3000 warning, health scope, and troubleshooting.
- `docs/demo/local-demo-runbook.md`: Timed 6–10 minute competition demonstration script, truthful claims, failure fallbacks, and rehearsal table.

Handoff paths:
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-031 status to `implemented`.
- `.agents/handoff/tasks/DLK-M3-031-local-demo-readiness.md`: Updated frontmatter status to `implemented` and completed implementation report.
- `.agents/handoff/reviews/DLK-M3-030-review.md`: Included accepted pending review record unchanged.

### Decisions made

- Avoided global `$ErrorActionPreference = "Stop"` for native console invocations in PowerShell scripts so that standard progress output on stderr (e.g. from Docker Compose) does not trigger false-positive terminating exceptions; evaluated `$LASTEXITCODE` explicitly.
- Used `alembic upgrade heads` in documentation to accommodate multiple head branches cleanly.
- Preserved existing development records in PostgreSQL volume `postgres_data` without running destructive volume wipes or automated tests against `dispenselens`.

### Verification results

1. PowerShell AST Syntax Parse (`System.Management.Automation.Language.Parser`):
   - `demo-preflight.ps1`: PARSED OK (0 errors)
   - `start-db.ps1`: PARSED OK (0 errors)
   - `verify-demo.ps1`: PARSED OK (0 errors)
2. Read-Only Preflight Check (`scripts/demo-preflight.ps1`):
   - Pre-startup run with free ports: Passed with exit code 0.
   - Controlled port-conflict run: Correctly detected occupied port 8000 (PID 45164 python), identified process, printed actionable warning without killing process, and returned exit code 1.
3. Database Startup & Health (`scripts/start-db.ps1`):
   - Succeeded from repository root and from parent directory.
   - `docker inspect --format "{{.State.Health.Status}}" dispenselens-postgres` reported `healthy`.
4. Development Migrations:
   - `.\.venv\Scripts\python.exe -m alembic upgrade heads` applied successfully with exit code 0.
5. Post-Startup Application Identity (`scripts/verify-demo.ps1`):
   - Backend identity verified: `service: dispense-lens-api`, `status: ok`, `version: 0.1.0`.
   - Frontend identity verified: `http://localhost:3001 (HTTP 200)` matching `DispenseLens` / `DispenseIQ` title/content. Returned exit code 0.
   - Controlled wrong-service run against port 3000 (Open-WebUI): Correctly failed with exit code 1 and reported `(Wrong local application detected at http://localhost:3000)`.
6. Health API Integration Test (`backend/tests/integration/test_health_api.py`):
   - `2 passed, 11 warnings in 2.38s`.
7. Frontend Static & Production Checks:
   - `npm run lint`: 0 errors, 0 warnings.
   - `npm run build`: Compiled successfully with Turbopack and TypeScript; all 13 routes generated.
8. Task Validation & Whitespace:
   - `validate_task.py`: Returned VALID.
   - `git diff --check`: Passed with 0 errors.

### Limitations and follow-up

- Production hosting, containerized application services, and automated CI/CD pipelines remain deferred for team release coordination.
- Live OpenAI provider execution remains an optional enhancement; deterministic fallback path is verified.

### Proposed commit message

`docs(demo): make local competition startup repeatable`
