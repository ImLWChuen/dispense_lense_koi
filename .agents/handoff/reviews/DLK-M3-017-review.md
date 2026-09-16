---
task_id: DLK-M3-017
reviewed_commit: d15c080b532cdbb03b62f81d910e8d41b83e7771
decision: changes_requested
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-017

## Decision

Changes requested for two bounded API error/validation defects. No diagnostic semantic changes are requested.

## Acceptance evidence

- Reviewed the exact committed API, schema, repository, ORM, migration, tests, and task report. Working tree was clean on backend-database at review start.
- The new route invokes the existing confirm_cause operation, persists confirmation history and revision within one transaction, and retains the unresolved issue condition. Repository append checks the current revision under a case row lock. Reconstruction restores confirmations with a revision cutoff.
- Tests cover explicit confirmation versus supporting checks, stale requests/replay, unknown causes, mixed revision history, persisted notes, and rollback with prior question/check history and an unrelated control case.
- Gemini reports migration 0005 applied, 14 confirmation API tests, 30 persistence tests, and 226 full backend tests passing. These are implementer-reported results; reviewer did not rerun database tests or migrations.
- Reviewer task validator returned VALID and committed diff whitespace inspection passed.

## Findings

### R1 — P2: Do not expose internal engine ValueErrors as client validation errors

backend/app/api/cases.py:804-815 wraps the entire engine.confirm_cause call in except ValueError and returns str(e) as HTTP 422. That operation first invokes diagnose and then performs further domain work; an internal ValueError, including a Pydantic validation error, is therefore exposed verbatim rather than reaching the sanitized HTTP 500 handler. For example, an engine dependency raising ValueError containing a private path would return that path to the client. The task explicitly requires unexpected internal failures to be sanitized 500 responses.

Separate known invalid-cause validation from unexpected engine failures using the existing candidate-cause contract; preserve Member 2 semantics. Only a known invalid request should return 422. Add an engine dependency-override regression with a valid cause and an internal ValueError containing a synthetic sensitive marker: require sanitized 500, no marker in the response, and no persisted changes. Retain unknown-cause 422 coverage.

### R2 — P2: Validate performer length before database persistence

backend/app/schemas/case.py:317-320 accepts confirmed_by without a length limit, while backend/app/models/case.py:427-431 and migration 0005 store it in VARCHAR(64). A valid-cause request with a 65-character performer passes request validation, then fails at PostgreSQL with a data-length error and returns 500. This is client-controlled invalid input and should be rejected as 422 before persistence.

Set the request's maximum length to the existing 64-character storage contract and document the limit. Add boundary coverage proving 64 characters persist faithfully and 65 characters return 422 with no confirmation or revision appended. Do not widen the database column or alter confirmation semantics to fix this.

## Follow-up

Carry R1 and R2 into the next bounded correction packet before releasing dependent feature work. No next or correction task generated in this review. No production edits, commits, pushes, or merges performed. Review and queue edits remain local and uncommitted.
