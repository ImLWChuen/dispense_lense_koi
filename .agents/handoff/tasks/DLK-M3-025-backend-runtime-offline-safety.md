---
task_id: DLK-M3-025
title: Restore safe backend startup and offline troubleshooting baseline
status: implemented
created_by: planner
assigned_to: Gemini 3.8 Flash in Antigravity
depends_on: [DLK-M3-024]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-025: Restore safe backend startup and offline troubleshooting baseline

## Objective

Establish a repeatable Member 3 backend baseline in which the declared dependencies install, the FastAPI service starts, the deterministic troubleshooting flow remains usable without an AI API key, local frontend port 3001 is allowed, and automated PostgreSQL tests use a separate disposable database without touching existing development records.

This is the first bounded increment of the next Member 3 stabilization stage. Lossless canonical check-history repair is intentionally reserved for a separate task after this one is reviewed.

## Current evidence

- Planning baseline: commit `005176dc994dc934e5e475163183f4b3c94fe25a` on `backend-database`, equal to local and remote-tracking `main` when inspected on 2026-09-19.
- `backend/pyproject.toml` declares `openai`, `opencv-python-headless`, and `python-multipart`, but the existing `backend/.venv` has not been synchronized; current unit-test collection stops with `ModuleNotFoundError: No module named 'openai'`.
- `backend/app/services/ai/llm_service.py` and `backend/app/core/config.py` use the merged OpenAI configuration (`OPENAI_API_KEY`, `OPENAI_MODEL`, with generic `LLM_*` aliases) and already intend graceful no-key fallback.
- `backend/tests/unit/test_teammate_integration_contracts.py` and the repository-root `.env.example` still assert or document the older Gemini provider contract. These are stale against the merged implementation.
- `backend/tests/unit/test_ai_outputs.py::test_explanation_service_offline_fallback` does not explicitly clear `OPENAI_API_KEY` and `LLM_API_KEY`, so it is environment-dependent.
- The default CORS list permits port 3000 but not port 3001. Port 3000 is occupied by the user's OpenWebUI; the DispenseLens frontend is to run locally on port 3001.
- Each PostgreSQL integration module currently contains a fallback that assigns `DATABASE_URL` to the `dispenselens` development database when the variable is absent. The safety allowlist also treats `dispenselens` as a disposable test name. This does not satisfy the decision to preserve existing records and use a separate disposable database.
- `backend/app/db/database.py` initializes the SQLAlchemy engine lazily, so a centralized pytest bootstrap can select the test destination before a connection is created.
- Existing untracked `.agents.zip` and `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md` belong to the user/planner. Preserve them and do not stage them as part of this task.

## Requirements

### 1. Dependency and application startup baseline

- Synchronize `backend/.venv` from the already-declared project dependencies with `pip install -e ".[dev]"`.
- Do not add, remove, upgrade, downgrade, or relax a dependency constraint unless the declared installation itself is proven invalid. If a dependency change appears necessary, stop and return to the planner with the exact failure.
- Verify the application imports and the health endpoint responds after dependency synchronization.
- Run `pip check` and record its actual result.
- Do not commit `.venv`, downloaded packages, caches, build output, or credentials.

### 2. Offline deterministic troubleshooting

- When both `OPENAI_API_KEY` and `LLM_API_KEY` are absent or blank, importing and starting the backend must not require an external AI service.
- A valid stateless diagnosis request must still return the deterministic ranked causes, numerical scores/confidence, evidence explanation, and applicable next question or check produced by the existing engine.
- The no-key path must not construct an OpenAI client or make an outbound request.
- LLM timeout/error behavior must continue to fall back to deterministic output without changing official rankings, scores, confirmation state, recovery state, or resolution state.
- Make existing offline tests independent of whatever API keys happen to exist in the developer's shell or `.env`.
- Treat the merged OpenAI provider/configuration as the current implementation contract. Remove stale Gemini expectations from tests and environment templates, but do not redesign the provider abstraction or diagnostic semantics.

### 3. Separate disposable PostgreSQL test destination

- Introduce one centralized pytest test-database bootstrap using `TEST_DATABASE_URL` as the explicit source for database-backed tests.
- Within the pytest process, database-backed tests may bind the application's `DATABASE_URL` to the validated `TEST_DATABASE_URL` before the lazy engine is created. Production/runtime configuration outside tests must continue to use `DATABASE_URL`.
- Database-backed tests must fail closed before connecting when `TEST_DATABASE_URL` is missing, malformed, remote, redirected through query parameters, or names a non-disposable database.
- The accepted local test database name is `dispenselens_test` or another name matching the existing explicit `test_*`, `*_test`, `test-*`, or `*-test` policy. The plain development database name `dispenselens` must no longer pass the test-destination safety check.
- If a development `DATABASE_URL` is also present, reject configuration when it resolves to the same database target as `TEST_DATABASE_URL`.
- Remove the per-module silent fallback to the development `dispenselens` database from the existing PostgreSQL integration suites; centralize the behavior rather than copying another fallback.
- Tests that do not need PostgreSQL, including health, configuration, and offline diagnosis tests, must remain runnable without `TEST_DATABASE_URL`.
- Document a non-destructive, repeatable way to create `dispenselens_test` in the existing local PostgreSQL service. Creating the missing test database is allowed; dropping/recreating `dispenselens`, deleting its rows, removing the Docker volume, or running migrations against it is prohibited.
- Apply Alembic migrations only to the disposable test database during verification. Existing development records and migration state must remain unchanged.

### 4. Local integration configuration

- Add `http://localhost:3001` and `http://127.0.0.1:3001` to the default local CORS origins while retaining the current compatible origins.
- Update both environment examples and backend startup documentation so they consistently describe:
  - development `DATABASE_URL` versus disposable `TEST_DATABASE_URL`;
  - optional OpenAI configuration and deterministic no-key behavior;
  - frontend port 3001, backend port 8000, and the matching CORS origins;
  - safe migration and test commands that cannot silently target the development database.
- Do not commit a real `.env` file or any actual API key.

## Interfaces and data contracts

- Public HTTP routes, request schemas, success/error response shapes, and status codes must remain unchanged.
- The deterministic engine remains the authority for rankings, scores, questions, checks, cause confirmation, recovery, and resolution.
- `OPENAI_API_KEY` and `OPENAI_MODEL` remain the provider-specific variables; `LLM_API_KEY` and `LLM_MODEL` remain supported aliases where the current implementation already supports them.
- `DATABASE_URL` remains the runtime/development database setting.
- `TEST_DATABASE_URL` is a test-runner setting only. It must not replace the runtime API contract or be loaded by production startup.
- No database schema, migration, persisted record, or diagnostic knowledge file may change in this task.

## Allowed paths

- `.env.example`
- `backend/.env.example`
- `backend/README.md`
- `backend/app/core/config.py` only for backward-compatible local CORS defaults
- `backend/tests/conftest.py` (new centralized test bootstrap)
- `backend/tests/unit/test_persistence_safety.py`
- `backend/tests/unit/test_teammate_integration_contracts.py`
- `backend/tests/unit/test_ai_outputs.py`
- `backend/tests/unit/test_runtime_baseline.py` or one equivalently focused new unit/integration test file
- Existing `backend/tests/integration/test_*.py` files only to remove their duplicated development-database fallbacks and delegate to the centralized test bootstrap
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/tasks/DLK-M3-025-backend-runtime-offline-safety.md`

## Prohibited scope

- Do not implement or modify image/CV analysis.
- Do not repair check-history persistence in this task; that is the next planned Member 3 increment.
- Do not change diagnostic rules, weights, cause meanings, question/check logic, knowledge JSON, or evaluation reference answers owned by Member 2.
- Do not modify frontend code owned by Member 1.
- Do not replace OpenAI with another provider or add live paid-API verification.
- Do not change public API contracts.
- Do not add or rewrite Alembic migrations or database models.
- Do not drop any database, table, row, Docker volume, or existing development record.
- Do not add vector retrieval, analytics, authentication, background workers, or machine control.
- Do not stage or commit `.agents.zip` or `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md`.
- Do not push, merge, rebase, create a pull request, or modify `main`.

## Implementation guidance

1. Confirm the active branch is `backend-database`, inspect the dirty tree, and preserve the two known untracked artifacts listed above.
2. Synchronize the existing backend virtual environment from `backend/pyproject.toml`. If installation fails because a declared constraint cannot resolve, stop and report rather than editing dependencies.
3. Add focused regression tests first for environment-independent offline behavior, OpenAI-aligned settings, port-3001 CORS, and fail-closed test-database selection.
4. Centralize test-database selection before any SQLAlchemy engine is created. Keep unit-only tests independent from PostgreSQL. Avoid importing test-only configuration into production modules.
5. Remove the repeated integration-test fallback that silently selects `/dispenselens`. Preserve each suite's existing fixture isolation and tracked cleanup behavior.
6. Update environment examples and backend documentation to match the verified implementation. Never include a real key or credential beyond the existing documented local-only Compose defaults.
7. Create `dispenselens_test` only if it is absent, using a non-destructive local PostgreSQL administration command. Do not recreate it when it already exists.
8. Temporarily target only `TEST_DATABASE_URL` while applying migrations and running PostgreSQL tests. Restore the shell's prior development `DATABASE_URL` after verification.
9. Run the focused checks, then the full backend suite. If Docker/PostgreSQL is unavailable, record the exact blocker and mark the task `blocked`; do not substitute SQLite or claim the database criteria passed.
10. Inspect the final diff and staged files, complete the implementation report, update `QUEUE.md`, and create one local commit only after all required checks pass.

## Acceptance criteria

- [x] `backend/.venv` installs the existing declared runtime and development dependencies successfully, and `pip check` reports no broken requirements.
- [x] `from app.main import app` succeeds after dependency synchronization.
- [x] `GET /api/v1/health` returns its existing successful payload.
- [x] With `OPENAI_API_KEY` and `LLM_API_KEY` explicitly absent, a valid stateless diagnosis succeeds with deterministic ranked causes, numerical scores, evidence explanation, and a supported next step.
- [x] The offline diagnosis test proves no OpenAI client/network call occurs.
- [x] External model failure still produces deterministic output and cannot alter official diagnostic state.
- [x] Settings/tests/environment examples consistently use the merged OpenAI configuration; stale Gemini provider assertions and template variables are removed.
- [x] Default CORS accepts both localhost forms of port 3001 and retains the existing accepted origins.
- [x] Database-backed tests require an explicit, structurally safe `TEST_DATABASE_URL` and bind to it before the application engine is created.
- [x] Missing, remote, redirected, non-test, plain `dispenselens`, and same-as-development test destinations fail before connection or cleanup.
- [x] PostgreSQL unit/integration verification runs against `dispenselens_test` (or another separately named approved test database), never against the existing development database.
- [x] Alembic reaches the current head on the disposable test database without creating or rewriting migrations.
- [x] Existing development records and schema are not mutated by setup, migration, or test execution.
- [x] Backend documentation gives one repeatable Windows PowerShell workflow for dependency synchronization, test-database creation, test migration, tests, and server startup on port 8000 with frontend port 3001.
- [x] Public API schemas/status codes and Member 2 diagnostic semantics remain unchanged.
- [x] The full backend test suite passes with zero failures against the disposable test database.
- [x] Task validation and whitespace checks pass, only authorized files are staged, and no remote Git operation occurs.

## Verification

Run from `backend/` unless stated otherwise:

1. Synchronize declared dependencies:
   `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`
2. Verify dependency consistency:
   `.\.venv\Scripts\python.exe -m pip check`
3. Verify application import:
   `.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"`
4. Run focused runtime/offline/configuration checks:
   `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_health_api.py tests/unit/test_ai_outputs.py tests/unit/test_teammate_integration_contracts.py tests/unit/test_runtime_baseline.py`
   If the new focused file uses a different planner-authorized name, substitute that actual path and record it.
5. Run test-destination safety checks without requiring a database connection:
   `.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_persistence_safety.py`
6. Set `TEST_DATABASE_URL` to the separate local disposable database documented by the implementation. Preserve the existing `DATABASE_URL`; do not overwrite it permanently.
7. Apply current migrations to the test destination only by temporarily presenting `TEST_DATABASE_URL` as `DATABASE_URL` to Alembic. Record the exact PowerShell command and result in the implementation report.
8. Run the focused real-PostgreSQL acceptance suites with the centralized test bootstrap:
   `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_persistence.py tests/integration/test_mvp_backend_acceptance.py`
9. Run the full backend suite against the disposable test database:
   `.\.venv\Scripts\python.exe -m pytest -q`

From the repository root:

10. Validate the task packet:
    `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-025-backend-runtime-offline-safety.md`
11. Run `git diff --check`.
12. Inspect `git status --short`, staged filenames, and the complete staged diff. Confirm `.agents.zip`, the planner progress report, environment files, dependency directories, and generated output are not staged.

## Planner decision boundaries

Return to the planner before:

- changing dependency versions or adding/removing a package;
- changing the AI provider, public API, database schema, migrations, or persisted data contract;
- modifying Member 2 diagnostic semantics or Member 1 frontend code;
- weakening the test-destination safety rules;
- deleting or recreating any database or Docker volume;
- implementing check-history repair, image/CV work, or any deferred feature;
- expanding beyond runtime/offline/test-isolation stabilization.

If local Docker/PostgreSQL cannot be made available, mark the task `blocked` with the exact observed command/error after completing any independent focused work. Do not create a success commit with unmet PostgreSQL acceptance criteria.

## Git instructions

Create one atomic local commit after every required check passes. Do not push, merge, rebase a shared branch, create or update a pull request, or change `main`.

Proposed commit message: `fix(backend): restore safe offline runtime baseline`

## Implementation report

Complete this section before the local commit.

### Summary

- Addressed review findings R1–R7 from `.agents/handoff/reviews/DLK-M3-025-review.md`:
  - **R1 (Migration environment restoration):** Updated `backend/README.md` to cleanly separate optional development database setup from disposable test migrations. Provided an explicit, non-destructive PowerShell pattern that validates destination safety, saves `$origDb = $env:DATABASE_URL`, temporarily presents `$env:TEST_DATABASE_URL` inside a `try` block, and reliably restores the original environment (or removes the variable) in a `finally` block before any test runner execution.
  - **R2 (Test isolation from .env loading):** Isolated offline unit and configuration tests from real developer `.env` files and shell variables. Added autouse fixtures in `test_runtime_baseline.py` and `test_teammate_integration_contracts.py` stubbing `_load_env_file()` and clearing API key aliases and CORS overrides. Added a synthetic `.env` parsing test (`test_load_env_file_synthetic_scenario`) using `tmp_path` to verify zero-dependency file parsing, quote stripping, and shell environment precedence with zero process leakage via `monkeypatch.setenv`. Blocked OpenAI client instantiation across the complete offline diagnosis flow.
  - **R3 (Exercised mocked provider failures):** Added `test_llm_timeout_preserves_deterministic_diagnostic_authority` and `test_llm_provider_error_preserves_deterministic_diagnostic_authority` in `test_runtime_baseline.py`. Configured an active `LLMService(api_key="synthetic-configured-key")` and mocked `client.chat.completions.create` to raise `APITimeoutError` and `OpenAIError`. Verified that the real `generate_text` exception handlers are exercised and that candidate causes, numerical scores, conclusions, `issue_condition`, and fallback explanation match the unconfigured baseline with exact deterministic parity.
  - **R4 (Rejection of ambiguous development destinations):** Hardened `assert_safe_test_database()` in `backend/tests/unit/test_persistence_safety.py` to parse `dev_url`, fail closed on `make_url` parse errors or invalid ports, and reject destination query overrides (e.g., `dbname`, `host`, `hostaddr`, `port`, `service`, `database`). Integrated this check into `bootstrap_test_database()` in `conftest.py` so rejection occurs before environment rebinding or engine creation. Added connection-free regression tests.
  - **R5 (In-process TestClient request preservation):** Removed global `httpx.Client.send` patch in `test_stateless_diagnosis_offline_without_api_keys`. Targeted patches specifically to `httpx.HTTPTransport.handle_request` and `httpcore.ConnectionPool.handle_request` to block outbound HTTP transport without interfering with Starlette `TestClient`'s in-process ASGI transport. Asserted that neither `OpenAI` client instantiation nor outbound HTTP transport methods were called during the complete stateless request.
  - **R6 (Real .env loader execution without duplicated parser):** Captured the real production loader `_real_load_env_file` before test fixture patching. Controlled all tested environment keys, pointed candidate resolution to `tmp_path`, invoked `_real_load_env_file()` directly against the synthetic `.env`, asserted proper parsing, quote-stripping, and shell variable precedence, and restored all environment mutations in a `finally` block with zero copied parser logic.
  - **R7 (Exit-code checked validation gating migrations):** Updated `backend/README.md` to pass `dev_url=os.environ.get('DATABASE_URL')` to `assert_safe_test_database`, immediately check `$LASTEXITCODE`, and throw before binding or running Alembic migrations. Checked Alembic exit code inside `try` with `finally` restoration. Added `test_migration_safety_gate_blocks_execution_on_rejected_destination` regression test and demonstrated with a synthetic rejected URL and migration stub that migration execution is never invoked upon validation failure.
- Synchronized declared dependencies in `backend/.venv` via `pip install -e ".[dev]"`; verified consistency with `pip check` ("No broken requirements found") and application import (`from app.main import app; print(app.title)` printed "DispenseLens API").
- Verified offline deterministic troubleshooting operation without AI keys: stateless diagnosis produces deterministic ranked causes, numerical scores, and explanation; verified zero OpenAI client instantiation or outbound network calls when unconfigured.
- Added Next.js frontend port 3001 origins (`http://localhost:3001` and `http://127.0.0.1:3001`) to default CORS origins in `backend/app/core/config.py`.
- Applied Alembic migrations to head (`0007_check_execution_history`) on `dispenselens_test`. Verified development database nonmutation via table row counts and sample identity checks showing no records or tables in `dispenselens` were altered.
- Ran all focused checks (41 passed), safety tests (24 passed), acceptance suites (50 passed), and the complete backend test suite (401 passed, 0 failed, 32 warnings).

### Files changed

- `backend/app/core/config.py`: Added `http://localhost:3001` and `http://127.0.0.1:3001` to `DEFAULT_CORS_ORIGINS`.
- `backend/tests/conftest.py`: Added centralized session bootstrap fixture `test_database_url` enforcing `TEST_DATABASE_URL` fail-closed safety, pre-rebinding validation against active `DATABASE_URL`, and lazy SQLAlchemy engine rebinding.
- `backend/tests/unit/test_persistence_safety.py`: Restricted `ALLOWED_TEST_DB_EXACT` to disposable names (`test`, `dispenselens_test`), removing `dispenselens`; added dev-separation conflict check and fail-closed rejection for ambiguous or malformed development database destinations. Added regression tests including migration safety gate verification.
- `backend/tests/unit/test_teammate_integration_contracts.py`: Added `isolate_teammate_contracts_env` autouse fixture; updated contract assertions from stale Gemini settings to merged OpenAI settings (`openai_api_key`, `openai_model`) and verified port 3001 CORS inclusion.
- `backend/tests/unit/test_ai_outputs.py`: Isolated `test_explanation_service_offline_fallback` from shell environment variables and verified default `ExplanationService()` instantiation fallback.
- `backend/tests/unit/test_runtime_baseline.py`: Added 14 focused unit tests covering offline diagnosis, no-client creation, mocked provider timeout/error resilience, synthetic `.env` parsing with real loader, CORS preflight/GET on port 3001, test DB bootstrap fail-closed behavior on plain dispenselens and ambiguous/malformed dev URLs, and non-DB endpoint independence.
- `backend/tests/integration/test_*.py` (11 files: `test_case_api.py`, `test_case_report_api.py`, `test_case_report_pdf_api.py`, `test_cause_confirmation_api.py`, `test_check_execution_api.py`, `test_check_result_api.py`, `test_mvp_backend_acceptance.py`, `test_persistence.py`, `test_question_answer_api.py`, `test_recovery_verification_api.py`, `test_recurrence_api.py`): Removed duplicated per-module development database fallbacks and delegated to `test_database_url`.
- `.env.example`, `backend/.env.example`: Documented `TEST_DATABASE_URL`, added port 3001 to CORS origins, and aligned LLM section with OpenAI.
- `backend/README.md`: Documented repeatable PowerShell commands for dependency synchronization, non-destructive test database creation, safe migration workflow using `try...finally` environment restoration and exit-code validation gating, test execution via `TEST_DATABASE_URL`, and port 8000/3001 server execution.
- `.agents/handoff/QUEUE.md`: Updated `DLK-M3-025` status to `implemented` with addressed review items R1–R7.
- `.agents/handoff/tasks/DLK-M3-025-backend-runtime-offline-safety.md`: Completed task packet report with fresh verification results and database nonmutation evidence.

### Decisions made

- **R1 (Try/Finally Migration Pattern):** Implemented temporary binding of `$env:DATABASE_URL = $env:TEST_DATABASE_URL` within a `try` block and guaranteed restoration of `$origDb` in a `finally` block. This prevents shell state contamination where `DATABASE_URL` would inadvertently remain set to `dispenselens_test`.
- **R2 (Layered Test Isolation):** Layered environment isolation with autouse fixtures in unit test suites to disable `_load_env_file()` and strip API key / CORS environment variables, while exercising synthetic `.env` parsing in an isolated `tmp_path` using `monkeypatch.setenv` to prevent cross-test contamination.
- **R3 (Actual Provider Failure Exercise):** Exercised `LLMService.generate_text` error paths using mocked `OpenAI` client raising `APITimeoutError` and `OpenAIError`, verifying deterministic parity against the unconfigured baseline across all candidate causes, numerical scores, conclusions, revision numbering, and issue condition.
- **R4 (Fail-Closed Ambiguous Dev Destination Rejection):** Rejected any `dev_url` with query parameters targeting destination overrides (`dbname`, `host`, `port`, `service`) or parsing errors before environment rebinding or engine creation, preventing subtle connection redirection to test databases.
- **R5 (Transport-Level Outbound Blocking):** Replaced global `httpx.Client.send` patch with mocks on `httpx.HTTPTransport.handle_request` and `httpcore.ConnectionPool.handle_request`, allowing Starlette's `_TestClientTransport` in-process dispatch while guaranteeing no outbound network traffic occurs.
- **R6 (Direct Production Loader Invocation):** Captured `_real_load_env_file` before patching to execute the actual production parser against synthetic temporary files, eliminating duplicated parsing logic and ensuring environment mutations are cleaned up in `finally`.
- **R7 (Exit-Code Validation Gating):** Enforced that the migration workflow checks `$LASTEXITCODE` immediately after Python validation runs with `dev_url`, throwing before environment binding or Alembic invocation if safety checks fail.
- Preserved existing development database `dispenselens` without mutating any existing records or schema.

### Verification results

- Step 1 (Dependency synchronization): `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"` -> Successful editable installation.
- Step 2 (Dependency check): `.\.venv\Scripts\python.exe -m pip check` -> "No broken requirements found."
- Step 3 (Application import): `.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"` -> "DispenseLens API".
- Step 4 (Focused checks): `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_health_api.py tests/unit/test_ai_outputs.py tests/unit/test_teammate_integration_contracts.py tests/unit/test_runtime_baseline.py` -> 41 passed in 2.01s.
- Step 5 (Safety checks): `.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_persistence_safety.py` -> 24 passed in 0.03s.
- Step 6 & 7 (Alembic on test database with exit-code validation gating and environment restoration):
  Command:
  ```powershell
  $origDb = $env:DATABASE_URL
  .\.venv\Scripts\python.exe -c "from tests.unit.test_persistence_safety import assert_safe_test_database; import os; assert_safe_test_database(os.environ.get('TEST_DATABASE_URL', ''), dev_url=os.environ.get('DATABASE_URL'))"
  if ($LASTEXITCODE -ne 0) {
      throw "Test database safety validation failed (exit code $LASTEXITCODE). Migration aborted."
  }
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
  Result: Successfully upgraded `dispenselens_test` to `0007_check_execution_history (head)`.
  Demonstrated migration gating with synthetic rejected URL: when `TEST_DATABASE_URL` targeted `dispenselens` or included `?dbname=...`, the validator exited with code 1, threw "Test database safety validation failed", and migration was never invoked (`Migration invoked: False`).
- Development Database Nonmutation Evidence:
  Table row counts and record identity checks captured before and after verification demonstrate that no records or tables in the development database `dispenselens` were altered:

| Table Name | Pre-Verification Row Count | Post-Verification Row Count | Pre-Verification Sample / Identity | Post-Verification Sample / Identity | Status |
|---|---|---|---|---|---|
| `alembic_version` | 1 | 1 | `version_num`: `0007_check_execution_history` | `version_num`: `0007_check_execution_history` | Unchanged |
| `cases` | 1 | 1 | `case_id`: `5891fc24-27b2-476f-a8d5-d6a2a4950663`, `defect_code`: `D03_INCONSISTENT_SIZE`, `condition`: `UNRESOLVED` | `case_id`: `5891fc24-27b2-476f-a8d5-d6a2a4950663`, `defect_code`: `D03_INCONSISTENT_SIZE`, `condition`: `UNRESOLVED` | Identical |
| `analysis_revisions` | 1 | 1 | `id`: `14471`, `case_id`: `5891fc24-...`, `rev`: 1, `defect`: `D03_INCONSISTENT_SIZE` | `id`: `14471`, `case_id`: `5891fc24-...`, `rev`: 1, `defect`: `D03_INCONSISTENT_SIZE` | Identical |
| `case_observations` | 2 | 2 | `id`: `16946` (undersized), `id`: `16947` (after_prolonged_operation) | `id`: `16946` (undersized), `id`: `16947` (after_prolonged_operation) | Identical |
| `case_cause_confirmations` | 0 | 0 | None | None | Clean |
| `case_check_executions` | 0 | 0 | None | None | Clean |
| `case_check_results` | 0 | 0 | None | None | Clean |
| `case_lifecycle_events` | 0 | 0 | None | None | Clean |
| `case_question_answers` | 0 | 0 | None | None | Clean |

- Step 8 (Focused real-PostgreSQL integration):
  `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_persistence.py tests/integration/test_mvp_backend_acceptance.py` -> 50 passed in 14.08s.
- Step 9 (Full backend suite):
  `.\.venv\Scripts\python.exe -m pytest -q` -> 401 passed, 32 warnings in 56.33s.
- Step 10 (Task validation): `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-025-backend-runtime-offline-safety.md` -> VALID.
- Step 11 (Whitespace check): `git diff --check` -> Clean with zero errors.
- Step 12 (Git status check): Cleanly staged only authorized files; `.agents.zip`, reviews, and generated artifacts remain unstaged.

### Limitations and follow-up

- Image/CV integration, bounded LLM runtime calls, and vector historical-case retrieval remain deferred per milestone boundaries.
- Lossless canonical check-history repair is reserved for the next task (`DLK-M3-026`).

### Proposed commit message

`fix(backend): resolve review findings R5-R7 for offline safety baseline`
