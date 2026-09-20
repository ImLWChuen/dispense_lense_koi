# Implementation Queue

## Current milestone

Final submission hardening and end-to-end demo acceptance

## Accepted prerequisite

- `DLK-M3-029` — Restart-safe technician troubleshooting and lifecycle workflow — **accepted**
  - reviewed commit: `9cb20fae5093b1d4e617fcccf7e54ae89be23b5a`
  - accepted outcome: restart-safe questions, checks, cause confirmation, recovery, verification, and recurrence
  - next-stage note from review: final end-to-end acceptance remained a separate decision

## Active task

- `DLK-M3-030` — Final submission hardening and end-to-end demo acceptance — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-030-submission-hardening.md`
  - branch: `backend-database`
  - depends on: accepted `DLK-M3-029`
  - implemented outcome:
    - repaired dynamic case detail with mutually exclusive loading, error/retry, and loaded detail states;
    - removed deferred Similar Cases from the competition demo path;
    - cleared full repository frontend lint gate (0 errors, 0 warnings across all files);
    - verified calibrated image → diagnosis → lifecycle → report/PDF → dashboard end to end;
    - resolved review findings R1-R5:
      - R1: implemented bounded observation and image provenance projection into AI-summary prompt (`PromptManager.project_safe_observations`, `PromptManager.get_case_summary_prompt`, `cases.py`, `explanation_service.py`), strictly rejecting raw bytes, base64 strings, file paths, and secrets; added focused tests covering prompt projection, safety rejection, mocked provider returning `source="llm"`, provider failure returning `source="deterministic"`, and case state invariance; live smoke executed secret-safely (live OpenAI call honestly recorded as blocked by missing `OPENAI_API_KEY` in local test environment, deterministic fallback verified);
      - R2: removed `Math.random()`, derived deterministic timeline keys from persisted fields plus stable lifecycle array index (`idx-0`, `idx-1`); verified identical deep equality when called twice without event IDs;
      - R3: removed hardcoded `technician` identity from all timeline entries (cause confirmation, recovery action, recovery verification, recurrence), rendering `Not recorded` or omitting the actor clause when absent; regression verified no `technician` or `Engineer` identity is generated;
      - R4: bounded and sanitized primary observation `value`, `observation_type`, and `source` using `_is_safe_text` with explicit text-length limits (64/200/64), capped at 50 observations in deterministic input order, strictly omitting raw bytes/bytearrays, base64 strings, file paths (Windows and Unix), secrets/credential markers, and overlength strings; preserved valid canonical values;
      - R5: guaranteed complete offline test isolation in `test_ai_summary_endpoint_case_state_invariance` with synthetic `OPENAI_API_KEY` and mocked `LLMService` across all summary requests; verified case state invariance.
  - implementer verification:
    - frontend: `test-case-detail-state.mjs` (7/7 passed), `test-image-upload-state.mjs` (7/7 passed), `test-reports-state.mjs` (9/9 passed), `test-diagnostic-workflow-state.mjs` (16/16 passed), `npm run lint` (0 errors, 0 warnings), `npm run build` (success, 13 routes compiled)
    - backend: `alembic upgrade heads` applied, AI summary projection suite (10 passed), calibrated vision suite (54 passed), technician lifecycle suite (89 passed), full backend suite (491 passed, 0 failed, 42 warnings in 65.04s)
    - task validation: VALID; git diff whitespace check passed
  - next step: submit local commit to ChatGPT reviewer for review; do not push or merge

## Explicitly deferred

Do not implement inside DLK-M3-030:

- vector/semantic historical-case similarity
- new AI/CV models
- D06 score-bearing vision semantics
- authentication/authorization
- new analytics infrastructure
- deployment redesign
- new testing frameworks
- database/schema changes

Only DLK-M3-030 is authorized for implementation.

After DLK-M3-030 is accepted, the competition-facing application may be treated as submission-ready unless the acceptance run identifies a new reproducible blocker.
