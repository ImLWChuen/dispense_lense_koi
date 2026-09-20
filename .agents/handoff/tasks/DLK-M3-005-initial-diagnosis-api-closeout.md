---
task_id: DLK-M3-005
title: Close out the initial diagnosis API contract and verification
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: []
feature_branch: backend-database
base_branch: main
---

# DLK-M3-005: Close out the initial diagnosis API contract and verification

## Objective

Resolve the bounded review findings from DLK-M3-004 so the initial diagnosis API can be reassessed for acceptance before persistence work begins. Keep the implemented API behavior and diagnosis engine unchanged; this task is limited to contract documentation, acceptance-test strength, and factual handoff-record corrections.

## Current evidence

- Read `.agents/handoff/reviews/DLK-M3-004-review.md`. The review decision is `changes_requested`, not because the endpoint architecture is defective, but because the documentation and tests do not fully prove the task's own acceptance contract.
- DLK-M3-004 implemented synchronous `POST /api/v1/diagnoses`, an injectable `DiagnosticEngine`, transport validation, canonical `app.*` imports, package-data support, and a stateless initial-analysis flow.
- In the reviewed snapshot, `backend/app/api/diagnoses.py` returns the sanitized 500 detail exactly as `An unexpected error occurred during diagnosis evaluation.`. Treat the implemented response text as canonical for this closeout; do not change application behavior merely to match stale documentation.
- `backend/app/schemas/diagnosis_api.py` reuses the domain `Observation` model. The externally accepted observation fields therefore include `id`, `observation_type`, `value`, `original_text`, `statement_type`, `source`, `confidence`, and `timestamp`, subject to the domain model's defaults/validation.
- `backend/tests/integration/test_diagnosis_api.py` currently uses unknown code `D01_BRIDGING` in the test named for “defect code alone”, so it exercises unknown-code validation instead of the distinct known-defect-with-no-evidence rule.
- The current independence test proves unique `case_id` values and revision number 1 but does not prove that generated observation/evidence IDs from one request cannot leak into another.
- The current direct-engine parity test compares cause identity, score, conclusion, and only supporting-evidence counts. It does not prove preservation of the actual evidence relations/provenance/score breakdown or the rest of the deterministic result contract.
- The supplied planner review replay passed the full backend snapshot (`24 passed`), but Gemini must run fresh verification in the actual Git checkout and record the actual output.
- The planner's review environment did not contain `.git` metadata. Before editing, inspect the actual branch, working tree, recent commits, and identify the local commit that contains DLK-M3-004. Do not guess or fabricate its hash.

This is a correction to DLK-M3-004. Its prerequisite is the presence of the implemented DLK-M3-004 commit in the current checkout; DLK-M3-004 does not need to be accepted first. Do not start PostgreSQL or another product feature in this task.

## Requirements

- Preserve the existing `POST /api/v1/diagnoses` runtime behavior, public transport schema, diagnostic engine behavior, and health endpoint. No application-code change is expected for this correction.
- Correct `docs/api/api-spec.md` so it describes the executable endpoint rather than an idealized or stale contract:
  - document the exact canonical generic 500 detail currently returned by the route;
  - show FastAPI/Pydantic 422 validation as a structured `detail` array, or clearly label any shortened validation example as illustrative rather than literal;
  - document the actual accepted `Observation` fields exposed by the reused domain model, including caller-supplied/defaultable `id` and `timestamp` plus `statement_type`, `source`, and `confidence`;
  - keep the stateless/transient-case-ID limitation explicit;
  - keep cause scores described as evidence-support scores, not calibrated probabilities;
  - replace the misleading “Real Execution Example” claim with either a genuinely captured response or a clearly labelled representative example whose generated UUIDs/timestamps were normalized for readability. Do not show the same generated UUID as both `case_id` and an observation ID unless that is actually produced by the endpoint.
- Strengthen `backend/tests/integration/test_diagnosis_api.py` so the review findings are directly executable:
  - use a real supported defect code such as `D01_TOO_LITTLE` to prove that a known defect code alone, with blank description and no observations, is rejected as insufficient evidence with HTTP 422;
  - retain a separate unknown-defect-code test;
  - prove independent identical submissions generate separate case IDs and separate generated evidence/observation identities, with each initial analysis starting at revision 1 and no identity from one run appearing in the other;
  - strengthen API-versus-direct-engine parity so it compares the semantic `DiagnosisResult` after removing only nondeterministic generated IDs/timestamps. The comparison must cover the returned evidence content and provenance, relations, strengths, explanations/contributions, missing evidence, score breakdowns, cause conclusions/scores, next question, next check, explanation, issue condition, warnings, and analysis-revision content rather than only evidence counts.
- Keep tests behavior-focused. A normalization helper may be added inside the integration test file; do not modify engine/domain implementation to make the test easier.
- Correct the factual DLK-M3-004 implementation report where it states an error response that differs from the executable endpoint. Preserve historical honesty: any tests newly added or rerun under DLK-M3-005 must be labelled as correction-task verification rather than rewritten as if they occurred during the original DLK-M3-004 implementation.
- Include the planner review record unchanged in the correction commit if it is currently an uncommitted handoff artifact.

## Interfaces and data contracts

Unchanged public interface:

- `POST /api/v1/diagnoses`
- request model: existing `InitialDiagnosisRequest`
- response model: existing `DiagnosisResult`
- malformed or semantically invalid initial request: HTTP 422 via FastAPI/Pydantic validation
- accepted but unidentifiable problem: ordinary HTTP 200 engine result with warning/null analysis fields
- unexpected engine failure: HTTP 500 with `{"detail":"An unexpected error occurred during diagnosis evaluation."}`
- endpoint remains stateless; returned `case_id` is transient and not retrievable

This task does not authorize narrowing the reused `Observation` transport model, changing provenance semantics, changing the generic error text, or changing any diagnosis-engine output. The architectural note about client-supplied provenance remains a future trust-boundary decision, not part of this correction.

## Allowed paths

- `backend/tests/integration/test_diagnosis_api.py`
- `docs/api/api-spec.md`
- `.agents/handoff/reviews/DLK-M3-004-review.md` - stage the planner record unchanged
- `.agents/handoff/tasks/DLK-M3-004-initial-diagnosis-api.md` - factual implementation-report correction/addendum only
- `.agents/handoff/tasks/DLK-M3-005-initial-diagnosis-api-closeout.md`
- `.agents/handoff/QUEUE.md`

## Prohibited scope

- No changes under `backend/app/`, knowledge JSON, scoring logic, symptom extraction, cause confirmation, question/check selection, package dependencies, database schema, persistence, authentication, CORS, uploads, reports, LLM integration, CV, retrieval, or frontend code.
- Do not redesign or narrow `InitialDiagnosisRequest` or `Observation` in this task.
- Do not change HTTP status codes, route paths, response models, error wording, or other public API behavior to make documentation/tests easier.
- Do not weaken, delete, or replace existing meaningful tests merely to obtain a passing suite.
- Do not start the PostgreSQL persistence milestone. It remains gated on reviewer acceptance of this closeout.
- Do not push, merge, rebase a shared branch, create/update a pull request, or change `main`.

## Implementation guidance

1. Perform implementation-handoff preflight. Confirm branch `backend-database`, inspect `git status`, recent commits, and the DLK-M3-004 implementation commit. Expected uncommitted changes should be planner handoff artifacts only. Preserve any unrelated user/teammate change and stop if it overlaps this task.
2. Set DLK-M3-005 and `QUEUE.md` to `in_progress` before implementation.
3. Strengthen the tests first. Prefer a small test-only normalization helper that converts the API JSON and direct `DiagnosisResult.model_dump(mode="json")` into comparable structures while replacing/removing only generated `case_id`, evidence `observation_id`, and analysis-revision timestamps. Do not normalize away fields that are part of the deterministic contract.
4. For state isolation, inspect generated evidence IDs in both responses and prove the two executions do not reuse one another's generated observation identity. Keep the test independent of ordering assumptions beyond the engine's documented result order.
5. Update `docs/api/api-spec.md` from the actual schema/behavior. If generated values in the response example are normalized, say so immediately above the example.
6. Correct the DLK-M3-004 implementation report only where it is factually inconsistent, and add a clearly labelled DLK-M3-005 correction addendum for newly gathered verification evidence. Do not rewrite history.
7. Run focused and full verification. If a strengthened parity test exposes a real API/engine mismatch that would require application or diagnostic code changes, stop and return `blocked` with the smallest reproducible difference instead of expanding scope.
8. Complete this task's implementation report, set task/queue status to `implemented`, inspect the staged diff and file list, and create one atomic local correction commit only after all required checks pass.

## Acceptance criteria

- [x] A valid known defect code alone (for example `D01_TOO_LITTLE`) with no description/observations is explicitly tested and returns HTTP 422 for insufficient evidence; unknown defect-code validation remains a separate passing test.
- [x] Two identical valid submissions are explicitly proven independent: distinct transient case IDs, independent revision-1 analyses, and no generated observation/evidence identity from one execution appears in the other.
- [x] API/direct-engine parity compares the semantic diagnosis result after excluding only nondeterministic generated IDs/timestamps and covers actual evidence content/provenance, score breakdowns, next-step fields, warnings/state, and analysis-revision content rather than counts alone.
- [x] `docs/api/api-spec.md` matches the executable 500 detail, accurately represents structured 422 validation, documents the actual accepted Observation schema, and truthfully labels any normalized response example.
- [x] DLK-M3-004's implementation report no longer contradicts the executable error contract and clearly distinguishes original evidence from DLK-M3-005 correction evidence.
- [x] Focused diagnosis/health integration tests and the complete backend test suite pass with actual counts/warnings recorded.
- [x] No application, engine, knowledge, dependency, database, frontend, or public API behavior changes are included.
- [x] No unrelated files, generated output, environments, secrets, or credentials are staged or committed.

## Verification

From `backend/` using the established environment:

1. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_diagnosis_api.py tests/integration/test_health_api.py`
2. `.\.venv\Scripts\python.exe -m pytest -q`
3. `.\.venv\Scripts\python.exe -c "from app.main import app; s=app.openapi(); assert '/api/v1/diagnoses' in s['paths']; assert 'post' in s['paths']['/api/v1/diagnoses']; print('diagnosis OpenAPI present')"`

From repository root:

4. `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-005-initial-diagnosis-api-closeout.md`
5. `git diff --check`
6. Inspect `git status --short`, the staged diff, and `git diff --cached --name-only` before committing; only allowed task paths may be staged.

Record the exact outputs/counts. If a required check cannot run, do not report success; mark the task `blocked` unless the failure is clearly environmental and the task packet explicitly permits proceeding (it does not currently permit skipping these checks).

## Planner decision boundaries

Return to the planner before changing application code, public API behavior, domain schemas, error semantics, diagnosis logic, knowledge, dependencies, database contracts, ownership boundaries, security/trust policy, or task scope. If stronger parity/isolation tests reveal a real implementation defect, report the failing normalized diff and stop rather than fixing it under this documentation/test closeout.

## Git instructions

Create one atomic local commit after all required checks pass. Do not push, merge, rebase a shared branch, create or update a pull request, or change the base branch.

Proposed commit message: `test(api): close out initial diagnosis contract`

## Implementation report

### Summary

Resolved the bounded review findings from DLK-M3-004 to close out the initial diagnosis API contract and verification. Strengthened integration tests in `backend/tests/integration/test_diagnosis_api.py` by: (1) explicitly testing that a valid known defect code alone (`D01_TOO_LITTLE`) with no observations or description is rejected with HTTP 422 for insufficient evidence while retaining a separate unknown-defect test; (2) asserting that identical submissions produce completely disjoint generated observation/evidence IDs across runs in addition to distinct case IDs and revision 1; and (3) adding a semantic normalization helper `_normalize_diagnosis_result` to verify complete API-versus-direct-engine parity across all domain fields (evidence content, provenance, relations, strengths, score contributions, score breakdowns, cause conclusions, questions, checks, warnings, and analysis revision) after stripping only nondeterministic generated IDs/timestamps. Aligned `docs/api/api-spec.md` with the executable endpoint by documenting the canonical 500 detail (`"An unexpected error occurred during diagnosis evaluation."`), showing structured 422 `detail` validation arrays, adding `id` and `timestamp` to the `Observation` table, and updating the representative execution example with distinct UUIDs and an explanatory note. Corrected the DLK-M3-004 implementation report to cite the canonical 500 detail and added a DLK-M3-005 closeout addendum.

### Files changed

- `backend/tests/integration/test_diagnosis_api.py`: Added `_normalize_diagnosis_result` helper, strengthened parity assertion across all domain outputs, added observation ID disjointness assertion to state isolation test, tested `D01_TOO_LITTLE` alone for insufficient evidence, and asserted on error detail messages.
- `docs/api/api-spec.md`: Documented `id` and `timestamp` in `Observation` schema, updated example to Representative Execution Example with explanatory note and distinct UUIDs, documented structured 422 validation arrays, and documented canonical 500 error string.
- `.agents/handoff/reviews/DLK-M3-004-review.md`: Included planner review record unchanged.
- `.agents/handoff/tasks/DLK-M3-004-initial-diagnosis-api.md`: Corrected 500 error text in report, added DLK-M3-005 addendum, and cleaned up trailing blank line.
- `.agents/handoff/tasks/DLK-M3-005-initial-diagnosis-api-closeout.md`: Updated status to implemented, checked all acceptance criteria, and completed implementation report.
- `.agents/handoff/QUEUE.md`: Updated active status to implemented.

### Decisions made

- **Test Normalization Helper:** Implemented `_normalize_diagnosis_result` strictly inside the test file to compare complete domain output parity without altering any engine or domain code.
- **State Isolation Verification:** Used set disjointness (`obs_ids_1.isdisjoint(obs_ids_2)`) across all candidate causes and analysis revisions to prove that transient observation identities from one run do not appear in another.
- **Canonical Error Text Alignment:** Kept application code untouched: the canonical 500 detail already returned by `backend/app/api/diagnoses.py` (`"An unexpected error occurred during diagnosis evaluation."`) was adopted across all documentation and reports.

### Verification results

- `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_diagnosis_api.py tests/integration/test_health_api.py`: 13 passed, 2 warnings in 0.54s.
- `.\.venv\Scripts\python.exe -m pytest -q`: 24 passed, 2 warnings in 0.64s.
- `.\.venv\Scripts\python.exe -c "from app.main import app; s=app.openapi(); assert '/api/v1/diagnoses' in s['paths']; assert 'post' in s['paths']['/api/v1/diagnoses']; print('diagnosis OpenAPI present')"`: Passed with output `diagnosis OpenAPI present`.
- `backend/.venv/Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-005-initial-diagnosis-api-closeout.md`: Output `VALID`.
- `git diff --check`: Passed with 0 errors.

### Limitations and follow-up

- **Statelessness:** Endpoint remains stateless and initial-only; no database persistence is introduced in this task.
- **Provenance Trust Boundary:** Domain `Observation` model accepts caller-supplied provenance fields (`source`, `statement_type`, `id`, `timestamp`), which should be reviewed before establishing an external production trust boundary.
- **Gated Milestone:** PostgreSQL persistence layer (DLK-M3-006) remains gated on reviewer acceptance of this closeout.

### Proposed commit message

`test(api): close out initial diagnosis contract`
