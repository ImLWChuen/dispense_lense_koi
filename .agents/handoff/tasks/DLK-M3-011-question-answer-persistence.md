---
task_id: DLK-M3-011
title: Persist follow-up question answers and append immutable analysis revisions
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-010]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-011: Durable question-answer revision foundation

## Objective

Establish the durable backend foundation required for the adaptive investigation loop: persist one technician question answer, reconstruct the complete diagnostic case state from PostgreSQL, and atomically append the resulting immutable analysis revision N+1.

This is a persistence/reconstruction increment only. It intentionally does **not** expose a public question-answer HTTP endpoint yet because Member 2 owns diagnostic question meaning and the current repository contains question-answer mappings that require owner alignment before arbitrary question answers are made technician-facing.

The system-visible outcome is that Member 3 can reliably load an existing durable case, preserve its previous answers and analysis history, invoke the existing `DiagnosticEngine.submit_question_answer(...)` for a known supported answer contract, and persist the answer + any newly generated observations + the new diagnosis snapshot without mutating earlier revisions.

## Current evidence

- DLK-M3-010 at `d94e8ea54837719a444a27af05f2eac71efcb34f` passed ChatGPT review. At implementer preflight, confirm `.agents/handoff/QUEUE.md` records that exact commit as accepted. Under the user's current review preference, no separate DLK-M3-010 review file exists or is required.
- The accepted durable-case flow stores `cases`, `case_observations`, and immutable `analysis_revisions` in PostgreSQL and exposes create/retrieve behavior through `/api/v1/cases`.
- `StructuredCase` already contains `previous_answers`, `previous_check_results`, and `analysis_revisions`.
- `DiagnosticEngine.submit_question_answer(case, answer)` appends the answer to `case.previous_answers`, converts supported answers to observations, invokes `diagnose(case)`, and appends the next in-memory analysis revision.
- The database currently does not persist `QuestionAnswer` history. This means a durable case cannot yet be faithfully reconstructed for follow-up questioning, especially for `UNKNOWN` or `NOT_APPLICABLE` answers that intentionally produce no observation.
- `AnalysisRevisionModel` already provides append-only `(case_id, revision_number)` uniqueness and stores the complete `DiagnosisResult` snapshot.
- Inspection of Member 2-owned code shows `_QUESTION_ANSWER_MAPPINGS` is not currently aligned with every definition in `knowledge/questions.json` (for example, Q04/Q05 semantics differ). Member 3 must not correct or reinterpret those mappings in this task.

## Requirements

- Add durable storage for technician `QuestionAnswer` history without changing Member 2's `QuestionAnswer` domain model or diagnostic semantics.
- Add repository support to reconstruct a `StructuredCase` from persisted case context, observations, prior question answers, immutable analysis revisions, current issue condition, and existing timestamps.
- Add a repository operation that atomically appends exactly one question answer and the resulting analysis revision N+1, including only observations that are newly introduced by that answer/re-diagnosis cycle.
- Preserve every prior observation and analysis revision unchanged.
- Record the revision number first affected by each newly persisted observation using the existing `first_seen_revision` contract.
- Persist answers even when the answer produces no observation (`UNKNOWN` / `NOT_APPLICABLE`), because answer history is required to prevent the question engine from re-asking an already answered question.
- Enforce an optimistic stale-revision contract at the repository boundary: the caller supplies `expected_revision`; the append succeeds only when it equals the latest persisted revision for that case.
- Serialize competing writes for the same case using PostgreSQL row locking or an equivalently strong transaction-local mechanism before checking/appending the next revision.
- A stale or duplicate submission must fail before creating a new answer row, observation, or analysis revision.
- Preserve atomic rollback: answer row, new observations, and revision N+1 either all become durable or none do.
- Do not expose a new HTTP endpoint in this task.
- Do not change question knowledge, answer-to-observation mappings, evidence scoring, question selection, or any other Member 2-owned diagnostic meaning.

## Interfaces and data contracts

### New persisted question-answer record

Add one PostgreSQL-backed model/table for durable question-answer history. The exact private class/table name may follow repository conventions, but the persisted contract must contain at least:

- `id`: database primary key;
- `case_id`: UUID foreign key to `cases`, cascade on case deletion;
- `question_id`: unrestricted domain string (`TEXT` unless an existing domain validation bound justifies otherwise);
- `answer_value`: unrestricted domain string (`TEXT`);
- `answer_text`: nullable unrestricted text;
- `source`: existing `EvidenceSource` value;
- `answered_at`: timezone-aware timestamp from `QuestionAnswer.timestamp`;
- `resulting_revision_number`: positive revision number created from this answer.

Add a uniqueness rule that prevents more than one persisted question-answer event from claiming the same `(case_id, resulting_revision_number)` in this one-answer-per-revision flow. Do **not** add a uniqueness constraint on `(case_id, question_id)` in this task; future product policy may permit correction/re-answer workflows and that decision belongs to a later contract.

`resulting_revision_number` must be greater than 1 because revision 1 is the initial diagnosis.

### Case reconstruction

Add a repository read operation with behavior equivalent to:

`load_structured_case(case_id: str) -> StructuredCase | None`

It must reconstruct, without diagnostic recalculation:

- case identity/context;
- defect code/name;
- issue condition;
- all persisted observations with original IDs, provenance, confidence, timestamps, and ordering semantics;
- all persisted question answers in revision/history order;
- all persisted analysis revisions in ascending revision order, reconstructed from the stored immutable snapshots;
- existing case creation timestamp;
- `previous_check_results=[]` for now because check-result persistence is a later milestone.

Do not infer prior answers from observations. Answers that map to no observation must still reconstruct correctly from their own table.

### Append operation

Add one repository operation with behavior equivalent to:

`append_question_answer_revision(case, answer, result, expected_revision)`

The private signature may vary, but the contract must:

1. verify case/result identity;
2. lock the persisted case row (or use an equivalently strong PostgreSQL transaction mechanism);
3. read the current latest persisted revision while protected by that lock;
4. reject if `expected_revision != latest_revision`;
5. require `result.analysis_revision.revision_number == latest_revision + 1`;
6. persist the `QuestionAnswer` linked to that new revision;
7. insert only observations whose domain observation IDs are not already persisted for the case, with `first_seen_revision = new_revision_number`;
8. append one new immutable `AnalysisRevisionModel` containing the complete `DiagnosisResult` JSON snapshot;
9. leave all earlier revision snapshots and observations unchanged;
10. participate in the caller's transaction when a session is injected, consistent with the existing repository pattern.

Define a small repository-level stale-revision exception (or equivalent explicit error type) that carries no secrets and does not prescribe an HTTP status yet. HTTP translation to `409 Conflict` is deferred to the endpoint task.

### Stale revision semantics

For a case whose latest durable revision is `N`:

- `expected_revision=N` + engine result revision `N+1` -> append is eligible;
- `expected_revision<N` -> reject as stale, no writes;
- engine result revision other than `N+1` -> reject as contract mismatch, no writes.

This establishes the concurrency contract for the later HTTP endpoint without releasing that endpoint yet.

## Allowed paths

- `backend/app/models/case.py`
- `backend/app/models/__init__.py`
- `backend/app/db/repository.py`
- `backend/alembic/versions/0003_question_answer_history.py` (or the next correct forward revision filename generated for this repository)
- `backend/tests/integration/test_persistence.py`
- a new focused repository integration test file under `backend/tests/integration/` if cleaner than extending `test_persistence.py`
- `docs/database/erd.md`
- `database/schema.sql` only if its current role requires a pointer/note update; Alembic remains schema authority
- `backend/README.md` only for persistence/migration commands or scope notes directly affected by this task
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/NEXT-STEPS.md`
- `.agents/handoff/tasks/DLK-M3-011-question-answer-persistence.md`

## Prohibited scope

- No public question-answer route or other HTTP contract.
- No edits to `backend/app/services/diagnosis/**`, `backend/app/knowledge/**`, question definitions, scoring, evidence semantics, or answer mappings.
- No troubleshooting-check persistence or submission flow.
- No root-cause confirmation or recovery verification.
- No frontend work.
- No LLM/CV/retrieval/report work.
- No authentication/authorization.
- No generic event-sourcing framework or broad workflow abstraction.
- No change to the existing durable create/retrieve API behavior.
- No new runtime dependency.
- No rewriting or squashing existing Alembic history; use one forward migration.
- No remote Git operations or base-branch changes.

## Implementation guidance

1. Perform implementation-handoff preflight and confirm DLK-M3-010 is accepted and DLK-M3-011 is the only `ready` task.
2. Inspect the exact current Alembic head; create one forward migration from that head for question-answer history.
3. Add the minimal ORM model and export required by the repository/tests.
4. Implement faithful `StructuredCase` reconstruction from persisted state. Reuse existing domain models and enum validation rather than inventing transport-only representations.
5. Implement the stale-safe append operation with case-level PostgreSQL locking before latest-revision comparison.
6. In integration tests, use the real existing `DiagnosticEngine` only through its public methods. For the answer-driven revision test, use a Member 2 mapping already demonstrated by the repository's engine tests (for example Q01 with `after_prolonged_operation`). Do not broaden the test into validating all question knowledge.
7. Add a separate `UNKNOWN` or `NOT_APPLICABLE` case proving an answer with no new observation is still persisted/reconstructed and advances an immutable revision through existing engine behavior.
8. Add stale/duplicate submission and rollback tests using fresh independent sessions to prove no partial writes.
9. Verify revision 1 remains byte/JSON-semantically unchanged after revision 2 is appended.
10. Update ERD/database documentation to describe the new answer-history table and its purpose.
11. Run the required real-PostgreSQL checks, complete the implementation report, inspect the staged diff, and create one atomic local commit.

## Acceptance criteria

- [x] A forward Alembic migration adds durable question-answer history without modifying prior migration files.
- [x] Valid unrestricted `question_id`, `answer_value`, and `answer_text` values round-trip without undocumented truncation.
- [x] `load_structured_case` reconstructs case context, observations, answer history, revisions, issue condition, and timestamps without invoking the diagnostic engine.
- [x] A real Q01 follow-up using `DiagnosticEngine.submit_question_answer(...)` can be persisted as revision 2 with its answer history and any new observation(s).
- [x] Newly introduced observations have `first_seen_revision == 2`; revision-1 observations retain `first_seen_revision == 1`.
- [x] Revision 1 remains unchanged after revision 2 is appended.
- [x] The complete revision-2 `DiagnosisResult` snapshot round-trips from PostgreSQL without lossy transformation.
- [x] `UNKNOWN` or `NOT_APPLICABLE` answer history persists even when it creates no observation, and reconstruction includes that answer.
- [x] A stale `expected_revision` is rejected with no new answer, observation, or revision row.
- [x] A duplicate competing append cannot create two revision-2 records for the same case.
- [x] Failure after some pending writes but before successful commit rolls back the answer/new observations/revision as one unit and preserves unrelated existing data.
- [x] Existing durable-case, persistence, safety, stateless diagnosis, and health tests continue to pass.
- [x] No Member 2 diagnostic meaning or public HTTP contract changes.
- [x] Only authorized files change and no remote Git operation occurs.

## Verification

Use the existing verified local PostgreSQL `DATABASE_URL` that satisfies the accepted test-destination safety policy.

From `backend/`:

1. `docker compose up -d postgres` from the repository root if the documented local PostgreSQL service is not already running.
2. `.\.venv\Scripts\python.exe -m alembic upgrade head`
3. `.\.venv\Scripts\python.exe -m alembic current`
4. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_persistence.py`
5. Run any new focused repository integration test file explicitly if one is added.
6. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_case_api.py`
7. `.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_persistence_safety.py`
8. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_diagnosis_api.py tests/integration/test_health_api.py`
9. `.\.venv\Scripts\python.exe -m pytest -q`

From repository root:

10. `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-011-question-answer-persistence.md`
11. `git diff --check`
12. Inspect `git status`, `git diff --cached --name-only`, and the staged diff before commit.

Stop and report `blocked` if real PostgreSQL verification cannot run. Do not substitute SQLite for required persistence verification.

## Planner decision boundaries

Return to the planner before:

- changing Member 2 question/answer mappings, question knowledge, scoring, or evidence semantics;
- changing the public HTTP API;
- changing the stale-revision contract defined here;
- adding a uniqueness rule that prevents future re-answer/correction behavior by question ID;
- storing check results or confirmation/recovery state;
- adding dependencies;
- changing accepted PostgreSQL test-safety policy;
- expanding into generic workflow/event architecture.

If implementation reveals that faithful `StructuredCase` reconstruction is impossible without changing a Member 2 domain contract, stop with the exact mismatch and proposed minimal decision. Do not patch around it by inventing diagnostic state.

## Git instructions

Create one atomic local commit after all required checks pass. Include the queue and this task packet according to the repository handoff policy. Do not push, merge, rebase a shared branch, create/update a pull request, or change `main`.

Proposed commit message: `feat(db): persist question answers and analysis revisions`

## Implementation report

Complete this section before the local commit.

### Summary

Implemented durable storage for technician `QuestionAnswer` history (`case_question_answers`), faithful `StructuredCase` reconstruction from PostgreSQL without diagnostic engine invocation (`load_structured_case`), and atomic optimistic-concurrency revision appending (`append_question_answer_revision`).
A forward Alembic migration (`0003_question_answer_history`) creates the `case_question_answers` table with unrestricted domain `TEXT` columns for `question_id`, `answer_value`, and `answer_text`, indexed `case_id` foreign key with cascade delete, check constraint `resulting_revision_number > 1`, and unique constraint on `(case_id, resulting_revision_number)`.
Reconstruction loads full case context, observations, previous answers, immutable analysis revisions, issue condition, and timestamps.
The append operation locks the case row (`with_for_update()`), checks `expected_revision == latest_revision` (raising `StaleRevisionError` on mismatch), verifies `result.analysis_revision.revision_number == latest_revision + 1`, stores the `QuestionAnswerModel`, inserts only newly introduced observations with `first_seen_revision = new_rev`, and appends the immutable `AnalysisRevisionModel` with full `DiagnosisResult` JSON snapshot.
Preserved Member 2's diagnostic semantics and did not add any public HTTP endpoint. All 19 persistence tests, 15 case API tests, 17 safety tests, 13 stateless/health tests, and the complete 75-test backend suite pass against real local PostgreSQL.

### Files changed

- `backend/app/models/case.py`: Added `QuestionAnswerModel` and `question_answers` relationship to `CaseModel`.
- `backend/app/models/__init__.py`: Exported `QuestionAnswerModel`.
- `backend/alembic/versions/0003_question_answer_history.py`: Forward migration adding `case_question_answers` table, constraints, and indexes.
- `backend/app/db/repository.py`: Added `StaleRevisionError`, `get_case_question_answers`, `load_structured_case`, and `append_question_answer_revision`.
- `backend/tests/integration/test_persistence.py`: Added schema assertions for `case_question_answers` and 8 comprehensive integration tests covering unrestricted string round-trip, complete state reconstruction, real Q01 follow-up persistence, UNKNOWN answer handling with zero new observations, stale revision rejection, contract mismatch rejection, duplicate competing revision rejection, and atomic rollback on partial write failure.
- `docs/database/erd.md`: Updated ERD diagram, table documentation, and architectural rationale for `case_question_answers`.
- `.agents/handoff/NEXT-STEPS.md`: Updated roadmap order 4 to record DLK-M3-011 as implemented.
- `.agents/handoff/tasks/DLK-M3-011-question-answer-persistence.md`: Checked acceptance criteria and completed implementation report.
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-011 status to `implemented`.

### Decisions made

- Schema naming: Table named `case_question_answers` consistent with `case_observations`. Columns `question_id`, `answer_value`, and `answer_text` use `TEXT` to prevent string truncation.
- One-answer-per-revision: Enforced via `UniqueConstraint("case_id", "resulting_revision_number")` and `CheckConstraint("resulting_revision_number > 1")`. No constraint was placed on `(case_id, question_id)` to keep future re-answer workflows open.
- Stale revision handling: Implemented `StaleRevisionError(Exception)` with `case_id`, `expected_revision`, and `current_revision` attributes. Operation acquires row-level lock (`with_for_update()`) and checks `expected_revision == latest_revision` before any writes.
- Observation deduplication: `append_question_answer_revision` queries existing `observation_id`s in the case and inserts only newly introduced observations, assigning `first_seen_revision = new_revision_number`. Existing observations retain their original `first_seen_revision`.
- Zero-observation answers: Answers with `UNKNOWN` or `NOT_APPLICABLE` advance revision history and store `QuestionAnswerModel` while producing zero rows in `case_observations`.
- Reconstruction: `load_structured_case` faithfully restores `StructuredCase` including enum types, original observation UUIDs, answer history in order, and analysis revisions validated from immutable `result_snapshot["analysis_revision"]`. DiagnosticEngine is never invoked on read.

### Verification results

- `alembic upgrade head`: Applied `0003_question_answer_history` cleanly to PostgreSQL.
- `alembic current`: Shows `0003_question_answer_history (head)`.
- `tests/integration/test_persistence.py`: 19 passed in 2.32s.
- `tests/integration/test_case_api.py`: 15 passed in 1.88s.
- `tests/unit/test_persistence_safety.py`: 17 passed in 0.05s.
- `tests/integration/test_diagnosis_api.py tests/integration/test_health_api.py`: 13 passed in 0.93s.
- Full backend test suite (`pytest`): 75 passed, 2 warnings in 3.67s.
- `validate_task.py`: Passed for DLK-M3-011 packet.
- `git diff --check`: Clean (0 errors).

### Limitations and follow-up

- No public question-answer HTTP endpoint was added in this task; technician-facing follow-up question endpoints remain deferred to a subsequent milestone after Member 2 owner alignment.
- Troubleshooting-check result persistence, cause confirmation, and recovery verification remain deferred to later tasks.

### Proposed commit message

`feat(db): persist question answers and analysis revisions`
