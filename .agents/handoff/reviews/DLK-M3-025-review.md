---
task_id: DLK-M3-025
reviewed_commit: f1db85435b177dd9961a14116900c03556a912de
decision: accepted
reviewed_by: planner
---

# Review: DLK-M3-025

## Decision

Accepted at f1db85435b177dd9961a14116900c03556a912de for the scoped backend runtime/offline/test-isolation task. This decision supersedes the historical changes-requested reviews below. No blocking findings remain within this task.

## Final correction acceptance

- R5 resolved: the offline API test blocks HTTPTransport/httpcore outbound transport, preserving TestClient's ASGI transport, and asserts neither provider construction nor outbound transport occurred.
- R6 resolved: the real loader is captured before fixture patching, restored for the temporary synthetic .env scenario, and invoked directly. The copied parser is removed; tested variables are controlled and environment mutations restored in finally.
- R7 resolved: the documented PowerShell workflow passes the development URL to validation, checks its exit code before binding/migration, checks Alembic's exit code, and restores the previous DATABASE_URL in finally. Gemini records a rejected-URL migration-stub demonstration. The added Python test proves validator rejection only; it is not automated execution of the PowerShell recipe.
- Earlier provider-failure parity, environment isolation, CORS, and test-destination corrections remain intact. No API, diagnostic semantics, dependency constraints, database models, or migrations changed in this correction.
- Gemini reports 41 focused checks, 24 safety tests, 50 persistence/acceptance tests, and 401 full-suite tests passing (32 warnings), plus test database migration head 0007. Reviewer inspected source/diff and ran task validation (VALID) and committed whitespace check (passed); backend/PostgreSQL tests were not independently rerun under the project role split.
- Development row counts, sample identities, and migration version are limited preservation evidence, not proof of equality of every field/schema object. No further database mutation is requested for this documentation limitation.
- This accepts DLK-M3-025 only. Canonical lossless check-history repair remains planned as DLK-M3-026; whole-project submission readiness is not established.
- Review and queue updated without production edits, local commit, push, merge, or a new task packet.

## Previous correction review (historical)

Changes requested on correction commit 9de39950086ae0dbfae62f28d456f2a61b57423e. Current outstanding corrections are R5-R7 below. Original findings are retained as history.

## Correction review

R3 is resolved by mocked APITimeoutError/OpenAIError completion failures and deterministic parity assertions. R4's reported URL overrides and parsing errors are rejected before rebinding. R2's environment isolation is improved. R1 now restores DATABASE_URL with try/finally, but validation must gate migrations.

Gemini reports 41 focused and 400 full-suite tests passed. These are not independently verified and conflict with R5 in the committed source. Reviewer checked installed Starlette/httpx source, task validation (VALID), and committed whitespace (passed). No application tests or database operations were run under the project role split.

### R5 - P1: Allow the in-process TestClient request

backend/tests/unit/test_runtime_baseline.py:65 patches httpx.Client.send to raise RuntimeError, then calls client.post inside the patch. Installed Starlette TestClient subclasses httpx.Client and inherits that send method. The test therefore raises before dispatching to FastAPI; it cannot demonstrate offline diagnosis success as committed.

Remove that global send patch. Block actual outbound transport/provider calls while allowing TestClient's in-process ASGI transport. Keep the OpenAI constructor assertion and assert the outbound transport mock was never called. Rerun this exact test, focused checks, and the full suite, replacing the reported results with fresh evidence.

### R6 - P2: Test the real .env loader

backend/tests/unit/test_runtime_baseline.py:216 attempts to restore _original_load_env_file, but that symbol does not exist anywhere in backend. The autouse fixture's no-op remains installed. The subsequent loop duplicates the parser and manually injects environment variables, so this test can pass with a broken production loader. Ambient OPENAI_MODEL/LLM_TIMEOUT_SECONDS can also interfere.

Capture the real loader before patching or provide a fixture opt-out. Control all tested environment keys, invoke the real loader against the temporary synthetic .env, and restore its environment mutations. Remove the copied parser; verify precedence without accessing real developer keys.

### R7 - P2: Stop migrations when validation fails

backend/README.md:88 runs Python validation but never checks its exit code. Ordinary PowerShell continues after native-command failure, so Alembic can run after destination rejection. Validation also omits dev_url, bypassing the separate-development-target check before migrations.

Validate against the effective development setting, immediately check the validator exit code and throw before binding/migration on failure. Check Alembic's exit code too, retaining try/finally restoration. Use a synthetic rejected URL and harmless migration stub to demonstrate migration is never invoked after rejection.

Development table counts and sample identity checks are useful limited evidence; do not label them comprehensive equality of every stored field/schema definition.

No next task or production correction was created. R5-R7 must be resolved before DLK-M3-026 is released. No commit, push, or merge was performed.

## Original review (historical)

## Acceptance evidence

- Production changes are limited to adding the two port-3001 CORS origins. Dependencies, API schemas, migrations, and diagnostic semantics are unchanged.
- All eleven PostgreSQL integration modules now depend on the centralized test_database_url fixture; the silent development-database fallback is removed.
- Plain dispenselens is rejected by the test naming guard. Environment templates use OpenAI and distinguish development and test URLs.
- Gemini reports dependency installation, pip check, app import, migration head 0007, 37 focused tests, 19 safety tests, 50 persistence/acceptance tests, and 392 full-suite tests passing. These are implementer-reported results; the reviewer did not rerun application or PostgreSQL tests under the project role split.
- Reviewer ran task validation (VALID) and committed whitespace inspection (passed).
- A reported development case count of one alone does not prove full record/schema equality before and after verification. Do not describe this count as comprehensive nonmutation proof.

## Findings

### R1 - P2: Restore the development environment after test migrations

backend/README.md:82-88 migrates the development database and then leaves DATABASE_URL set to dispenselens_test. Following the next Running Tests section sets TEST_DATABASE_URL to the same target, which the new bootstrap correctly rejects. This is not a repeatable setup sequence and conflicts with the task's test-only migration boundary.

Separate optional development setup from this verification workflow. Validate the test URL before Alembic, save the original DATABASE_URL, temporarily bind the test URL inside try/finally, and restore its original value or absence before pytest. Show and verify the exact sequence without mutating development records or migrations.

### R2 - P2: Isolate offline tests from .env loading

backend/tests/unit/test_ai_outputs.py:161 and backend/tests/unit/test_runtime_baseline.py:35-99 delete API-key variables, but Settings.load() calls _load_env_file() again. A developer's .env key is therefore reintroduced before LLMService checks availability. The new stateless test can make a real provider request; other offline assertions fail. The same issue remains in test_teammate_integration_contracts.py's offline test. Default-settings/CORS assertions also inherit user overrides.

Use controlled test settings or prevent real .env loading within these tests while explicitly controlling both key aliases and the relevant settings. Add a synthetic .env scenario and block provider construction/network access around the complete offline diagnosis request, not just the separate LLMService unit test. Do not edit or read real keys into test output.

### R3 - P2: Exercise an actual provider failure

backend/tests/unit/test_runtime_baseline.py:92-116 names and describes timeout/error resilience, but constructs an unavailable LLMService and never injects a failure. It only repeats the no-key scenario, so it cannot support the implementation report's failure-resilience claim.

Mock a configured provider's completion call to raise a timeout and a provider error without network access. Compare deterministic cause IDs, scores, conclusions, and issue state with a no-key baseline, and assert the fallback explanation. Use the real LLMService error-handling path and record only behavior actually exercised.

### R4 - P2: Fail closed when the development destination is ambiguous

backend/tests/unit/test_persistence_safety.py:117-140 compares only the development URL authority/path and silently ignores parsing errors. A development URL such as postgresql+psycopg://user:pass@localhost:5432/dispenselens?dbname=dispenselens_test and a test URL ending /dispenselens_test are treated as different even though the database override selects the same target. Test URLs reject overrides, but the development side of the separation comparison does not.

Reject ambiguous development URLs (including destination query overrides and parse failures), or resolve their effective destination correctly before allowing tests. Add connection-free regression tests asserting rejection before environment rebinding or engine creation. Preserve existing loopback normalization and safe-destination checks.

## Follow-up

Correct R1-R4 within the current review scope and update the implementation report with fresh verification. Do not release DLK-M3-026 until accepted. No next/correction task packet was created, per the user's review workflow; these requirements must be carried forward if a planner later creates one. Only this review record and queue were edited. No production fix, commit, push, or merge was performed.
