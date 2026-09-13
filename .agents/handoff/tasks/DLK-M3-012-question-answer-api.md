---
task_id: DLK-M3-012
title: Expose technician question-answer submission API
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-011]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-012: Technician question-answer submission API

## Objective

Expose the accepted adaptive question-answer workflow through a minimal durable HTTP endpoint.

A client must be able to submit one technician answer for an existing durable diagnostic case, have the backend:

1. load and faithfully reconstruct the persisted `StructuredCase`;
2. validate the requested question and answer using Member 2's accepted question-answer contract;
3. apply the existing `QuestionAnswerHandler` / diagnostic-engine answer workflow;
4. generate the next immutable diagnosis revision;
5. atomically persist the question-answer history, any newly generated observations, and revision N+1;
6. return the updated durable diagnostic state.

This task exposes existing accepted behavior. It must **not** redefine diagnostic meaning.

## Current evidence

DLK-M3-011 has passed review and is the persistence/revision foundation for this task.

The synchronized `main` already contains Member 2's aligned question-answer semantics for Q01-Q15, including:

- knowledge-aligned answer keys;
- `UNKNOWN` handling without fabricated evidence;
- `NOT_APPLICABLE` handling without fabricated evidence;
- preservation of user hypotheses as unconfirmed hypotheses;
- answer-to-observation generation;
- answer-driven diagnosis rerun;
- next-question selection that excludes already answered questions.

DLK-M3-012 must reuse those semantics rather than reproduce them in the HTTP layer.

## Requirements

Implement exactly one new durable workflow endpoint:

`POST /api/v1/cases/{case_id}/answers`

The endpoint submits **one question answer** against the current durable case state.

Do not add batch-answer submission in this task.

## Interfaces and data contracts

Define an explicit request model containing at minimum:

- `question_id`
- `answer`
- `expected_revision`

### `question_id`

- Must identify one of the currently supported diagnostic questions.
- Do not hard-code a second independent list of valid questions inside the route if the existing Member 2 contract already provides the authority.
- Unknown/unsupported question IDs must fail cleanly as a client error.

### `answer`

- Must be interpreted by the existing Member 2 question-answer contract.
- The HTTP layer must not translate, normalize, invent, or reinterpret diagnostic meaning beyond ordinary schema serialization/deserialization.
- `UNKNOWN` and `NOT_APPLICABLE` must retain Member 2's accepted semantics.
- Invalid answers for a valid question must be rejected without creating a new revision.

### `expected_revision`

This is required optimistic-concurrency input.

The request must only succeed if `expected_revision` matches the case's current persisted revision at the time the atomic update is applied.

A stale request must not append:

- a question-answer history row;
- new observations;
- a new analysis revision;
- any other partial state.

## Endpoint behavior

### Successful flow

Expected orchestration:

`HTTP request`
→ `load current durable case`
→ `verify expected_revision`
→ `reconstruct StructuredCase`
→ `apply existing question-answer handler / engine workflow`
→ `produce updated DiagnosisResult / revision N+1`
→ `atomically append answer + observations + new revision`
→ `return persisted updated state`

Use existing domain and persistence APIs whenever possible.

Do not reimplement Member 2's diagnostic logic inside the API route, schema, or repository.

### Response

Return `200 OK` for a successful answer submission.

The response should expose the durable updated case state needed by the frontend to continue the investigation.

At minimum include:

- `case_id`
- submitted question-answer record or an equivalent explicit persisted representation
- current revision number
- newly updated persisted diagnosis snapshot
- current observations/evidence state as already exposed by the durable case contract, if that contract is reused
- next question, if any
- next troubleshooting check, if any
- current cause conclusions / issue condition as already represented by `DiagnosisResult`

Prefer reuse or extension of the existing durable case response contract rather than creating an unrelated parallel representation.

The response must reflect what was actually committed.

## Status and error contract

Use clear, deterministic HTTP outcomes.

At minimum:

- `200 OK` — answer accepted, revision N+1 committed
- `404 Not Found` — case does not exist
- `409 Conflict` — `expected_revision` is stale / does not equal the current persisted revision
- `422 Unprocessable Entity` — malformed request schema or answer/question combination rejected by the existing contract, where appropriate
- `500 Internal Server Error` — unexpected engine/persistence failure

Do not leak:

- database URL
- DB credentials
- SQL
- stack traces
- local filesystem paths
- secrets
- raw internal exception messages that expose infrastructure details

If the current codebase already has a consistent error envelope, reuse it.

## Diagnostic ownership boundary

Member 2 owns diagnostic meaning.

DLK-M3-012 must not modify or duplicate:

- question definitions;
- valid answer semantics;
- `QuestionAnswerHandler` mappings;
- answer-to-observation mappings;
- evidence rules;
- cause scoring;
- contradiction/support semantics;
- duplicate-evidence semantics;
- next-question selection logic;
- troubleshooting-check recommendation logic;
- cause-confirmation semantics;
- issue-condition semantics.

If the endpoint cannot be implemented without changing one of those contracts, stop and return the exact blocker to the planner.

## Persistence requirements

Reuse the accepted DLK-M3-011 persistence path.

A successful answer submission must durably preserve:

- the answer history entry;
- any observations generated by the accepted handler;
- observation provenance;
- `first_seen_revision` / equivalent accepted revision metadata;
- immutable earlier revisions;
- the complete new diagnosis snapshot;
- monotonically increasing revision number.

### Atomicity

Answer submission is one transaction.

If any part fails, none of the new state may survive.

### Immutability

Revision N must remain byte/semantically unchanged after revision N+1 is created, except for representation details that are explicitly outside stored snapshot content.

### Idempotence / duplicate submission safety

This task does not require a general idempotency-key system.

However:

- stale `expected_revision` must prevent accidental replay after a successful answer;
- re-submitting the same request with the old `expected_revision` must return `409` and must not append another revision.

## Repeated-answer policy

Do not invent a new repeated-answer semantic in the API.

Use the accepted Member 2 / DLK-M3-011 behavior.

At minimum, the endpoint must not create score inflation or duplicate evidence beyond what the accepted domain layer already permits.

If an already-answered question is invalid under the existing contract, surface that cleanly.
If the existing contract permits replacement/re-answering, do not implement replacement semantics unless they are already explicitly supported by DLK-M3-011 and Member 2's accepted logic.

Return to the planner if this area is ambiguous in implementation.

## Allowed paths

- `backend/app/api/routes/questions.py` or the existing question/case workflow route module
- API router registration module only if needed
- `backend/app/schemas/` files needed for the answer request/response contract
- `backend/app/db/repository.py` only if the accepted DLK-M3-011 persistence interface needs the smallest HTTP-facing integration helper
- `backend/app/db/session.py` only if required for the existing FastAPI DB dependency
- existing case reconstruction/persistence module introduced by DLK-M3-011
- `backend/tests/integration/test_question_answer_api.py`
- existing question-answer/revision tests only when required for regression coverage
- existing diagnosis/case API tests only when required for regression coverage
- `docs/api/api-spec.md`
- `backend/README.md` only if the local API workflow needs a small documented update
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/NEXT-STEPS.md` only to record milestone progression
- `.agents/handoff/tasks/DLK-M3-012-question-answer-api.md`

If an edit outside these paths is necessary, stop and return to the planner before changing it.

## Prohibited scope

Do not implement:

- troubleshooting-check result submission;
- action/check outcome-to-evidence mappings;
- root-cause confirmation endpoint;
- issue recovery verification endpoint;
- report/PDF generation;
- image/CV;
- LLM interpretation;
- historical/similar-case retrieval;
- authentication/authorization;
- frontend integration;
- list-all-answers endpoint;
- generic answer CRUD;
- answer deletion;
- case deletion/update;
- WebSockets/background jobs;
- new dependencies;
- database schema/migration changes unless a blocker is returned to the planner first.

Do not weaken the accepted PostgreSQL test-destination safety policy.

## Implementation guidance

1. Run full implementation-handoff preflight.
2. Confirm DLK-M3-011 is accepted and DLK-M3-012 is the only `ready` task.
3. Confirm the accepted DLK-M3-011 commit in `QUEUE.md` and read its implementation report. Under the user's current review preference, no separate DLK-M3-011 review file exists or is required.
4. Read Member 2's current:
   - question definitions;
   - `QuestionAnswerHandler`;
   - relevant `DiagnosticEngine` answer workflow;
   - current tests.
5. Define the HTTP request/response contract before implementing the route.
6. Reuse the accepted case reconstruction + revision append persistence path.
7. Add `expected_revision` conflict handling at the durable transaction boundary.
8. Add real PostgreSQL integration tests.
9. Prove no diagnostic semantics changed.
10. Update executable API documentation.
11. Run focused and complete verification.
12. Complete the implementation report and create one atomic local commit.

## Acceptance criteria

### Happy path

- [x] Existing durable case accepts a valid question answer.
- [x] Endpoint returns `200`.
- [x] Current revision advances exactly by one.
- [x] One durable answer-history record is appended.
- [x] Member 2's real answer handler is used.
- [x] Any generated observations are persisted with correct provenance.
- [x] Newly generated observations retain accepted revision metadata.
- [x] Complete updated diagnosis snapshot is persisted.
- [x] Previous revision remains immutable.
- [x] Response is semantically equivalent to persisted updated state.

### Adaptive behavior

- [x] A valid answer can change ranked-cause evidence/score only according to Member 2's existing logic.
- [x] Updated `next_question` comes from the existing engine and does not select an already answered question where the accepted engine excludes it.
- [x] `UNKNOWN` creates answer history and a new revision but does not fabricate diagnostic evidence.
- [x] `NOT_APPLICABLE` creates answer history and a new revision but does not fabricate diagnostic evidence.
- [x] A user-hypothesis answer does not become confirmed root cause merely because it was submitted.

### Concurrency / stale writes

- [x] Correct `expected_revision` succeeds.
- [x] Stale `expected_revision` returns `409`.
- [x] Stale submission appends no answer, observation, or revision.
- [x] Replaying a previously successful request using the old revision returns `409`.
- [x] Revision numbers remain monotonic.

### Failure and validation

- [x] Missing case returns `404`.
- [x] Unsupported question ID is rejected without durable mutation.
- [x] Invalid answer for a supported question is rejected without durable mutation.
- [x] Induced persistence failure rolls back answer + observations + revision atomically.
- [x] Unexpected internal errors expose no infrastructure secrets.

### Regression

- [x] Durable case create/retrieve API remains unchanged.
- [x] Stateless `/api/v1/diagnoses` remains unchanged.
- [x] Existing DLK-M3-011 persistence/revision tests pass.
- [x] Member 2 question-answer tests pass unchanged.
- [x] Existing persistence and test-safety tests pass.
- [x] No migration/schema change occurs.
- [x] Only authorized files change.
- [x] No remote Git operation occurs.

## Required PostgreSQL integration scenarios

At minimum cover:

1. **Valid answer creates revision 2**
   - create a durable case;
   - submit the case's current recommended question with a valid answer;
   - assert `200`;
   - assert revision changes from 1 to 2;
   - reload durable state and verify the answer + revision 2.

2. **Evidence-producing answer**
   - select a stable Member 2 question/answer pair known to create evidence;
   - verify exact observation semantics and provenance after reload;
   - verify diagnosis result reflects the accepted Member 2 behavior.

3. **UNKNOWN**
   - submit `UNKNOWN`;
   - answer history persists;
   - revision advances;
   - no fabricated evidence observation is added for the question answer.

4. **NOT_APPLICABLE**
   - same expectations as UNKNOWN regarding diagnostic evidence.

5. **Stale revision**
   - successfully submit one answer;
   - submit another request using the prior revision number;
   - expect `409`;
   - verify counts/state unchanged after the rejected request.

6. **Invalid answer**
   - valid question, unsupported answer;
   - expect client error;
   - no answer/revision/observation appended.

7. **Unknown question**
   - unsupported question ID;
   - expect client error;
   - no mutation.

8. **Missing case**
   - valid-looking unknown case ID;
   - expect `404`.

9. **Atomic rollback**
   - induce failure at the persistence seam;
   - verify no partial appended state.

10. **Prior revision immutability**
    - capture revision 1 snapshot;
    - append answer/revision 2;
    - reload revision 1 and prove unchanged.

11. **API regression**
    - existing case create/retrieve and stateless diagnosis APIs continue passing.

## API documentation requirements

Update `docs/api/api-spec.md` with:

- exact route;
- request schema;
- valid answer example;
- successful `200` response shape;
- `404` example;
- `409` stale-revision example;
- validation behavior;
- explicit optimistic concurrency semantics;
- explicit note that one successful answer creates one new immutable analysis revision;
- `UNKNOWN` / `NOT_APPLICABLE` behavior;
- no invented fields.

Examples labeled as real execution output must actually come from the implemented API.

## Verification

Use the accepted verified local PostgreSQL test database.

From `backend/` run the task-relevant commands, including at minimum:

1. Apply migrations to current head:
   `.\.venv\Scripts\python.exe -m alembic upgrade head`

2. Member 2 question-answer tests:
   run the existing focused question-answer / revision tests unchanged.

3. New HTTP integration tests:
   `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_question_answer_api.py`

4. DLK-M3-011 persistence/revision tests:
   run the existing focused tests covering question-answer persistence and revision append.

5. Existing case API:
   run the current durable case API tests.

6. Existing diagnosis + health APIs:
   run current focused suites.

7. Persistence integration tests.

8. Persistence safety tests.

9. Complete backend suite:
   `.\.venv\Scripts\python.exe -m pytest -q`

10. Inspect OpenAPI and verify:
    - durable case routes remain;
    - answer endpoint appears with intended status codes/schema;
    - stateless diagnosis route remains unchanged.

From repository root:

11. Validate the task packet:
    `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-012-question-answer-api.md`

12. `git diff --check`

13. Inspect `git status`, staged file names, and staged diff before commit.

If real PostgreSQL verification cannot run, mark the task `blocked`; do not substitute SQLite for required integration proof.

## Planner decision boundaries

Return to the planner before:

- changing Member 2 diagnostic semantics;
- changing question IDs or answer values;
- changing answer-to-observation mappings;
- changing database schema/migrations;
- adding dependencies;
- changing case/revision identity semantics;
- adding troubleshooting-check APIs;
- adding cause confirmation or recovery APIs;
- changing the public durable-case contract in a breaking way;
- relaxing accepted PostgreSQL safety rules.

## Git instructions

After all acceptance criteria pass:

- complete the implementation report;
- set DLK-M3-012 and `QUEUE.md` to `implemented`;
- inspect staged names and full staged diff;
- create exactly one atomic local commit.

Proposed commit message:

`feat(api): add durable question answer workflow`

Do not push, merge, rebase, create/update a PR, or modify `main`.

## Implementation report

### Summary

Implemented the durable technician question-answer submission workflow via `POST /api/v1/cases/{case_id}/answers`. The endpoint validates submitted questions and answers against Member 2's accepted `QuestionAnswerHandler`, advances the diagnostic state via `DiagnosticEngine.submit_question_answer`, enforces optimistic concurrency locking via `expected_revision`, and atomically commits the question answer, any derived observations, and the resulting immutable analysis revision to PostgreSQL using `CaseRepository.append_question_answer_revision`.

### Files changed

- `backend/app/schemas/case.py`: Defined `SubmitAnswerRequest`, `QuestionAnswerRecord`, and `CaseAnswerResponse` extending `DurableCaseResponse`.
- `backend/app/schemas/answer.py`: Re-exported question answer schemas for modular access.
- `backend/app/api/cases.py`: Implemented `submit_case_answer` endpoint with UUID validation, optimistic concurrency checks, Member 2 contract integration, atomic persistence, and comprehensive error mapping.
- `backend/tests/integration/test_question_answer_api.py`: Added 16 integration tests verifying OpenAPI registration, revision progression, observation provenance, UNKNOWN/NOT_APPLICABLE handling, 409 stale-revision rejection, 422 input/question rejections, 404 missing case handling, atomic rollback, and prior revision immutability.
- `docs/api/api-spec.md`: Added Section 4 documenting endpoint specification, request/response models, validation rules, HTTP status codes, and real execution payloads from PostgreSQL 16.
- `backend/README.md`: Documented the new endpoint, test command, and concurrency behavior.
- `.agents/handoff/QUEUE.md`: Advanced task status from `in_progress` to `implemented`.
- `.agents/handoff/NEXT-STEPS.md`: Recorded milestone progression for DLK-M3-012.
- `.agents/handoff/tasks/DLK-M3-012-question-answer-api.md`: Checked off all acceptance criteria and completed implementation report.

### API contract implemented

- **Route:** `POST /api/v1/cases/{case_id}/answers`
- **Request:** `SubmitAnswerRequest`
  - `question_id`: `string` (must match supported question registry Q01–Q15)
  - `answer`: `string` (valid option for question, or `UNKNOWN`/`NOT_APPLICABLE`; accepts `answer_value` alias)
  - `expected_revision`: `int >= 1` (optimistic locking token matching current case revision)
  - `answer_text`: `string | null` (optional technician statement)
- **Response (`200 OK`):** `CaseAnswerResponse`
  - `case_id`, `description`, `material`, `method`, `defect_code`, `defect_name`, `issue_condition`, `created_at`
  - `observations`: all observations persisted for the case with `first_seen_revision` and `source` provenance
  - `initial_diagnosis`: immutable revision-1 diagnosis snapshot
  - `diagnosis`: updated revision N+1 diagnosis snapshot with ranked causes, scores, and evidence
  - `current_revision`: current revision number (`N + 1`)
  - `submitted_answer`: `QuestionAnswerRecord` for the accepted answer
  - `previous_answers`: all question answers persisted for the case
  - `next_question`: recommended next question (excluding already answered questions)
  - `next_check`: recommended next troubleshooting check
- **Error Codes:**
  - `404 Not Found`: Case does not exist in the database.
  - `409 Conflict`: `expected_revision` does not equal current persisted revision (stale write / replay).
  - `422 Unprocessable Entity`: Malformed UUID, unknown question ID, invalid answer value, or validation error.
  - `500 Internal Server Error`: Persistence or engine failure with sanitized error message.

### Diagnostic reuse decisions

- Delegated all question ID and answer value validation directly to Member 2's `QuestionAnswerHandler`.
- Used `DiagnosticEngine.submit_question_answer` to compute the next revision without duplicating scoring, cause ranking, or question selection.
- Preserved `UNKNOWN` and `NOT_APPLICABLE` zero-observation semantics (no fabricated evidence).
- Preserved user hypothesis handling (user hypotheses are stored as observations but never converted to confirmed causes).
- Reused `DiagnosticEngine.question_engine.select_next_question` which excludes already answered questions.

### Persistence/concurrency decisions

- Enforced optimistic concurrency via `expected_revision`.
- Pre-checked `expected_revision` against loaded case revision, and enforced row-level lock check (`with_for_update()`) inside `CaseRepository.append_question_answer_revision`.
- Injected FastAPI database session is committed atomically after append, rolling back on any failure.
- `StaleRevisionError` maps cleanly to `409 Conflict`.

### Verification results

- `backend/.venv/Scripts/python.exe -m pytest tests/integration/test_question_answer_api.py -v`: 16 passed in 3.14s.
- `backend/.venv/Scripts/python.exe -m pytest tests/integration/ -v`: 69 passed in 7.71s.
- `backend/.venv/Scripts/python.exe -m pytest -v`: 121 passed in 7.38s.
- OpenAPI specification validated: `/api/v1/cases/{case_id}/answers` present with 200, 404, 409, 422 responses.
- Task packet validation: `validate_task.py` passed with `VALID`.
- `git diff --check`: clean (no whitespace or lint warnings).

### Limitations and follow-up

- Supports one question answer per request; batch-answer submission is not in scope.
- Check result submission and explicit cause confirmation remain planned for future milestones.

### Proposed commit message

`feat(api): add durable question answer workflow`
