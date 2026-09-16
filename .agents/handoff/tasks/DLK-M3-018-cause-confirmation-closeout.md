---
task_id: DLK-M3-018
title: Close cause-confirmation error handling and performer validation
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-017]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-018: Cause-confirmation API closeout

## Objective

Close the two bounded API defects blocking acceptance of DLK-M3-017 without changing diagnostic semantics, persistence structure, or the confirmation workflow.

This task must:

1. preserve known invalid-cause requests as client validation errors while routing unexpected internal engine `ValueError`s to a sanitized HTTP 500 response; and
2. enforce the existing 64-character `confirmed_by` storage contract at request validation time.

DLK-M3-017 remains unaccepted until this correction is implemented and reviewed.

## Current evidence

DLK-M3-017 was reviewed at commit:

`d15c080b532cdbb03b62f81d910e8d41b83e7771`

The review returned `changes_requested`.

### R1 — Internal engine ValueErrors can leak

The cause-confirmation endpoint currently catches every `ValueError` raised around `engine.confirm_cause()` and returns `str(e)` as HTTP 422.

That incorrectly treats unexpected internal engine/domain failures as client input problems and can expose sensitive internal details.

Required distinction:

- known invalid/unknown cause request -> `422`
- unexpected internal engine/domain failure -> sanitized `500`

### R2 — `confirmed_by` lacks the existing storage boundary

The request currently accepts unrestricted `confirmed_by` text while PostgreSQL stores the field in `VARCHAR(64)`.

Required request contract:

- preserve current nullability/minimum semantics;
- maximum length 64;
- 64 characters -> accepted and persisted exactly;
- 65 characters -> `422` before persistence.

Do not widen the database column.

## Scope

This is a bounded correction task.

Do not add new product capabilities.

Do not begin:

- issue recovery / verification;
- resolved / recurred workflow;
- report generation;
- frontend work;
- LLM/CV;
- historical retrieval.

## Requirements

### R1 requirements — sanitize unexpected engine failures

#### Known invalid cause behavior

Preserve the existing client-facing behavior for a cause ID that is not valid under the accepted cause-confirmation contract.

Known invalid cause requests must:

- return `422 Unprocessable Entity`;
- return a safe client-readable validation message;
- create no confirmation history;
- create no revision;
- mutate no durable state.

Do not change Member 2's cause semantics.

#### Unexpected engine failure behavior

Do not wrap the whole `engine.confirm_cause()` call in generic `except ValueError -> 422`.

Use the existing candidate-cause/domain contract to distinguish a known invalid request at the appropriate validation seam.

After a valid cause request has passed normal client validation, an unexpected internal `ValueError` from the engine/domain path must:

- return sanitized `500 Internal Server Error`;
- not expose `str(e)`;
- not expose synthetic sensitive markers;
- not expose filesystem paths;
- not expose DB/SQL/internal implementation details;
- create no confirmation history;
- create no analysis revision;
- mutate no durable case state.

Do not convert an unexpected failure into 422 only because the Python exception type is `ValueError`.

#### R1 regression test

Add an API regression using the existing dependency-override/test seam:

1. create a valid durable case;
2. choose a valid confirmable cause;
3. override/inject the engine dependency so the confirmation path raises a `ValueError` containing a synthetic sensitive marker;
4. call the confirmation endpoint;
5. assert:
   - response is `500`;
   - response body does not contain the marker;
   - response body does not contain the full internal exception;
   - confirmation history is unchanged;
   - revision count/current revision is unchanged;
   - prior durable case state remains unchanged.

Retain unknown-cause `422` coverage so both sides of the distinction are proven.

### R2 requirements — enforce confirmed_by storage contract

Align the request schema with the accepted database contract.

Set the request-side maximum length for `confirmed_by` to:

`64`

Do not modify:

- ORM column length;
- migration 0005;
- confirmation-history schema.

Preserve current nullability/minimum-length behavior unless already defined otherwise.

#### R2 boundary tests

Add API integration coverage proving:

##### Exactly 64 characters

- valid cause;
- `confirmed_by` exactly 64 characters;
- request succeeds;
- performer value persists exactly with no truncation;
- confirmation event is created;
- revision advances exactly once.

##### Exactly 65 characters

- valid cause;
- `confirmed_by` exactly 65 characters;
- request returns `422`;
- rejection occurs before persistence;
- no confirmation event is appended;
- no revision is appended;
- current revision is unchanged;
- prior state remains unchanged.

The 65-character test must fail specifically because of performer-length validation.

## Interfaces and data contracts

No product API redesign is authorized.

Preserve:

- `POST /api/v1/cases/{case_id}/cause-confirmations`;
- success response contract;
- stale revision `409`;
- missing case `404`;
- unknown/invalid cause `422`;
- explicit confirmation semantics;
- unresolved issue-condition invariant;
- confirmation-history persistence;
- global revision sequencing;
- rollback behavior.

The only intended visible changes are:

1. unexpected internal engine failures -> sanitized `500`;
2. `confirmed_by` >64 characters -> `422`.

## Diagnostic ownership boundary

Do not change:

- `confirm_cause()` semantics;
- candidate-cause generation;
- cause ranking;
- scoring;
- evidence rules;
- question-answer semantics;
- troubleshooting-check semantics;
- issue-resolution/recovery semantics.

If R1 cannot be implemented without changing diagnostic meaning, stop and return the blocker to the planner.

## Implementation guidance

- Validate the requested cause through the existing candidate-cause contract before invoking the engine.
- Let unexpected exceptions from the engine reach the existing sanitized internal-error response path.
- Express the 64-character performer limit in the request schema so invalid input is rejected before persistence.
- Preserve the existing repository, ORM, migration, response, and diagnostic contracts.

## Allowed paths

- `backend/app/api/cases.py`
- `backend/app/schemas/case.py`
- `backend/tests/integration/test_cause_confirmation_api.py`
- existing confirmation test helpers/fixtures only when required
- `docs/api/api-spec.md`
- `backend/README.md` only if performer/error behavior is documented there
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/NEXT-STEPS.md` only for closeout progression
- `.agents/handoff/reviews/DLK-M3-017-review.md` (include unchanged)
- `.agents/handoff/tasks/DLK-M3-017-cause-confirmation-api.md` only for narrow implementation-report corrections if needed
- `.agents/handoff/tasks/DLK-M3-018-cause-confirmation-closeout.md`

Return to the planner before editing outside this scope.

## Prohibited scope

Do not change:

- ORM models;
- Alembic migrations;
- database schema;
- dependencies;
- repository persistence/transaction semantics;
- Member 2 semantics;
- PostgreSQL destination-safety policy.

Do not add:

- recovery/verification API;
- confirmation revocation;
- report generation;
- authentication;
- frontend code;
- LLM/CV;
- generic CRUD.

## Acceptance criteria

### R1

- [x] Known invalid/unknown cause still returns `422`.
- [x] Known invalid cause creates no durable mutation.
- [x] Valid cause + unexpected internal `ValueError` returns `500`.
- [x] Internal error text is not reflected in the response.
- [x] Synthetic sensitive marker is absent from the response.
- [x] Unexpected failure creates no confirmation event.
- [x] Unexpected failure creates no revision.
- [x] Prior case state remains unchanged.
- [x] No diagnostic semantic changes are introduced.

### R2

- [x] Request schema enforces maximum `confirmed_by` length 64.
- [x] Exactly 64 characters succeeds.
- [x] The 64-character value round-trips exactly.
- [x] 65 characters returns `422`.
- [x] 65-character rejection appends no confirmation event.
- [x] 65-character rejection appends no revision.
- [x] No database column/migration change occurs.

### Regression

- [x] Successful cause confirmation still works.
- [x] Supporting checks still do not auto-confirm causes.
- [x] Cause confirmation still does not resolve the issue.
- [x] Stale revision remains `409`.
- [x] Missing case remains `404`.
- [x] Confirmation rollback tests pass.
- [x] Question-answer and check-result workflows pass.
- [x] Persistence and safety suites pass.
- [x] Complete backend suite passes.
- [x] Only authorized files change.
- [x] No remote Git operation occurs.

## API documentation requirements

Update `docs/api/api-spec.md` so it accurately states:

- `confirmed_by` maximum length is 64;
- known invalid cause -> `422`;
- unexpected internal confirmation failure -> sanitized `500`;
- error responses do not echo internal exception details.

Do not invent response fields.

## Verification

Use the accepted verified local PostgreSQL test database.

From `backend/`, run at minimum:

1. focused cause-confirmation API suite:
   `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_cause_confirmation_api.py`

2. existing confirmation persistence/rollback coverage;

3. check-result API + semantic suites;

4. question-answer API/revision suites;

5. durable case + diagnosis + health suites;

6. persistence suite;

7. persistence-safety suite;

8. complete backend suite:
   `.\.venv\Scripts\python.exe -m pytest -q`

9. inspect OpenAPI and confirm:
   - confirmation endpoint remains;
   - `confirmed_by` maxLength is 64;
   - documented response statuses remain consistent.

From repository root:

10. validate task:
    `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-018-cause-confirmation-closeout.md`

11. `git diff --check`

12. inspect `git status`, staged names, and full staged diff before commit.

If real PostgreSQL verification cannot run, mark the task `blocked`.

## Planner decision boundaries

Return to the planner before:

- changing cause-confirmation semantics;
- widening `confirmed_by` storage;
- changing migration 0005;
- changing repository transaction semantics;
- changing successful response structure;
- adding dependencies;
- expanding into recovery verification.

## Git instructions

After all acceptance criteria pass:

- complete the DLK-M3-018 implementation report;
- mark DLK-M3-018 and `QUEUE.md` as `implemented`;
- inspect staged files/diff;
- create one atomic local correction commit.

Proposed commit message:

`fix(api): close out cause confirmation contract`

Do not push, merge, rebase, create/update a PR, or modify `main`.

## Implementation report

### Summary

Closed out both R1 and R2 findings from the DLK-M3-017 review without altering diagnostic semantics, ORM models, or database schemas:
1. **R1**: Disentangled client-side invalid-cause validation from unexpected engine errors. Validated `cause_id` against candidate causes (`case.analysis_revisions[-1].ranked_causes` or `get_causes_for_defect(case.defect_code)`) returning HTTP 422 for unknown causes before calling the engine. Removed the broad `except ValueError -> 422` wrapper around `engine.confirm_cause()`, allowing any unexpected engine/domain errors to reach the sanitized HTTP 500 handler without leaking sensitive markers or file paths.
2. **R2**: Enforced maximum length 64 on `confirmed_by` in `SubmitCauseConfirmationRequest` matching the database `VARCHAR(64)` constraint, rejecting 65-character inputs with HTTP 422 before persistence and verifying that 64-character inputs round-trip faithfully.

### Files changed

- `backend/app/schemas/case.py`: Added `max_length=64` to `confirmed_by` field on `SubmitCauseConfirmationRequest` and validation in `validate_payload()`.
- `backend/app/api/cases.py`: Added candidate cause pre-validation in `submit_case_cause_confirmation()` and removed broad `ValueError -> 422` catch around `engine.confirm_cause()`.
- `backend/tests/integration/test_cause_confirmation_api.py`: Added OpenAPI schema assertion for `maxLength == 64`, added `test_engine_internal_value_error_returns_sanitized_500_and_does_not_mutate`, `test_confirmed_by_exactly_64_chars_succeeds_and_persists_exactly`, and `test_confirmed_by_65_chars_rejected_with_422_before_persistence`.
- `docs/api/api-spec.md`: Documented 64-character limit for `confirmed_by`, invalid cause 422 error, and sanitized 500 internal server error contract.
- `.agents/handoff/QUEUE.md`: Marked DLK-M3-018 as `implemented`.
- `.agents/handoff/tasks/DLK-M3-018-cause-confirmation-closeout.md`: Marked status as `implemented` and filled report.

### R1 internal-error handling

- Identified candidate cause IDs before engine invocation:
  `candidate_cause_ids = [c.cause_id for c in case.analysis_revisions[-1].ranked_causes] if (case.analysis_revisions and case.analysis_revisions[-1].ranked_causes) else [c.id for c in get_causes_for_defect(case.defect_code)]`
- If `request.cause_id not in candidate_cause_ids`, raises HTTP 422 with safe message:
  `"Cannot confirm cause '{request.cause_id}': not found in current ranked causes. Available causes: {candidate_cause_ids}"`
- Removed `except ValueError as e: raise HTTPException(422, detail=str(e))` around `engine.confirm_cause()`. Unexpected engine exceptions propagate to the outer `except Exception:` block, returning a sanitized HTTP 500 (`"An unexpected error occurred while submitting the cause confirmation."`) without leaking internal exception text.
- Verified in `test_engine_internal_value_error_returns_sanitized_500_and_does_not_mutate` using `MagicMock` raising `ValueError("internal engine detail C:/private/model/path/secret-key-12345")`: endpoint returns HTTP 500, marker is completely absent from response, and fresh session proves zero mutation.

### R2 performer-length validation

- Added `max_length=64` to `confirmed_by: str = Field(default="technician", max_length=64, ...)` in `SubmitCauseConfirmationRequest`.
- Validated that OpenAPI documentation generates `maxLength: 64`.
- Verified boundary behavior in integration tests:
  - `test_confirmed_by_exactly_64_chars_succeeds_and_persists_exactly`: 64 characters succeeds with HTTP 200, persists into PostgreSQL without truncation, and advances revision to 2.
  - `test_confirmed_by_65_chars_rejected_with_422_before_persistence`: 65 characters returns HTTP 422 at request validation; fresh session verifies 0 confirmations and case remains at revision 1 with zero mutation.

### Verification results

- `pytest tests/integration/test_cause_confirmation_api.py`: 17 passed in 4.71s.
- `pytest tests/integration/test_persistence.py`: 30 passed in 5.40s.
- Check-result & semantic suites: 78 passed in 5.22s.
- Question-answer suites: 34 passed in 3.57s.
- Case, diagnosis, health suites: 28 passed in 2.07s.
- Persistence safety suite: 17 passed in 0.23s.
- Full backend suite (`pytest -q`): 229 passed, 0 failed in 16.71s.
- `validate_task.py`: Passed (VALID).
- `git diff --check`: Passed (zero whitespace warnings).

### Limitations and follow-up

- Issue recovery / post-correction verification remains deferred to subsequent milestones.
- Resolved / recurred state workflow remains deferred.
- Frontend cause-confirmation integration remains deferred.

### Proposed commit message

`fix(api): close out cause confirmation contract`
