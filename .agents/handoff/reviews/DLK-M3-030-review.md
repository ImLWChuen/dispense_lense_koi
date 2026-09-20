---
task_id: DLK-M3-030
reviewed_commit: 747235695fa9777a8b9f84f4b47e66844b50a98f
decision: accepted
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-030

## Decision

Accepted after reviewing correction commit `747235695fa9777a8b9f84f4b47e66844b50a98f`. R1-R5 are resolved. The case-detail flow is truthful and deterministic, persisted IMAGE evidence reaches the bounded AI-summary prompt, unsafe prompt values are rejected with explicit size/count limits, and the automated summary tests cannot contact a real provider. Live OpenAI execution remains an honestly recorded optional limitation because no API key is configured locally; deterministic fallback and the mocked provider-success path are verified.

## Final correction review: `747235695fa9777a8b9f84f4b47e66844b50a98f`

- R4 resolved: primary observation type, value, and source now pass bounded safety checks; raw bytes, data-image/base64 content, paths, credential markers, blanks, and overlength strings are omitted.
- Projection is capped at 50 valid observations in deterministic input order, with type/value/source limits of 64/200/64 characters.
- Reviewer adversarial reproduction confirmed that prohibited base64 and 5,000-character values no longer survive, while the first 50 canonical observations remain ordered and unchanged.
- R5 resolved: the state-invariance test holds the `LLMService` mock across successful, unavailable, and exception paths while a synthetic API key is present. No real provider client or request is reachable from that test.
- Focused AI-summary suite: 10 passed.
- Independent full backend suite: 491 passed with 42 warnings.
- Frontend source was unchanged by this correction; the previously verified 39 state regressions, full lint, and production build remain applicable.
- Task validation returned `VALID`, committed whitespace inspection passed, and no new dependency, migration, schema, diagnostic-weight, or public-response change was introduced.

## Correction review: `3b45af45c716d65f1b7b950da9734f720dba9f0a`

### R4 — Primary observation values bypass the bounded projection filter (high)

- `PromptManager.project_safe_observations` sanitizes whitelisted provenance values through `_sanitize_val`, but `backend/app/services/ai/prompt_manager.py:218-222` converts the primary observation `value` directly to an unrestricted string.
- The observation schema and database column allow arbitrary text. A persisted value containing a data-image/base64 string, path, credential-like text, or thousands of characters therefore reaches the provider even though the helper and implementation report claim those values are rejected.
- Reviewer reproduction confirmed `data:image/png;base64,QUJDREVGRw==` survived the projection and a 5,000-character value was returned unchanged.
- Apply the same bounded text sanitizer to the primary value. Cap both projected observation count and individual text lengths so the projection is actually bounded. Skip an unsafe/incomplete item or use a neutral omission marker; never forward the rejected content. Extend the safety test so prohibited content is placed in the primary `value`, not only in unwhitelisted metadata, and cover list/field limits.

### R5 — Offline state-invariance test can call the real OpenAI provider (medium)

- `backend/tests/unit/test_ai_summary_projection.py:377-391` patches `LLMService` only for the first request. The second request occurs after the patch exits and assumes the environment has no API key.
- On a developer or CI host with `OPENAI_API_KEY`, this nominal unit/integration test can make a real billable network request and may return `source: "llm"`, breaking the assertion and the project's offline-test contract.
- Keep `LLMService` mocked for both calls. Explicitly configure the second mocked service as unavailable or make it return `None`, then assert deterministic fallback and zero real client/network construction. The suite must remain deterministic even when the parent environment contains an API key.

### Resolved in this correction

- R1 evidence flow is resolved: the API and `ExplanationService` obtain persisted observations, project whitelisted text/image provenance, and include the projection in the summary prompt without changing public response fields or deterministic diagnostic state.
- The live-provider limitation is now reported honestly: the local environment has no configured API key, so live execution remains blocked while deterministic fallback is verified.
- R2 is resolved: missing lifecycle IDs use stable array-index suffixes, and repeat derivation is covered by deep-equality regression.
- R3 is resolved: blank actors no longer generate a technician/engineer identity, while persisted actor names remain visible.

## Findings

### R1 — Live OpenAI and IMAGE-evidence acceptance was not demonstrated (high)

- The implementation report records `source: 'deterministic'`, while the task requires the live smoke to return the documented LLM source when the configured provider is working. A deterministic fallback is useful failure behavior, but it is not evidence that a live OpenAI call succeeded.
- The report says the key was present but does not identify a sanitized provider failure or explain why the endpoint fell back. This does not satisfy the task's alternative requirement to record external failure honestly.
- A reviewer-side secret-safe check found the OpenAI package available but no API key configured through the repository's supported environment loader. No secret value was read or printed. This explains the current deterministic fallback but contradicts treating the live-provider criterion as passed.
- More fundamentally, `backend/app/api/cases.py:2700-2708` builds the summary prompt from case metadata, confirmed causes, and attempted checks only. `backend/app/services/ai/prompt_manager.py:147-170` has no observation/evidence input. The existing summary path therefore cannot reference persisted IMAGE evidence or its provenance, even when the durable case contains it.
- Add a bounded, text-only projection of persisted observations to the summary prompt. Include observation type, normalized value, source, confidence when present, revision, and a safe subset of image-analysis provenance; never include raw image bytes, local paths, or secrets. Add focused tests proving IMAGE evidence is included in the prompt, deterministic state is unchanged, LLM success returns `source: 'llm'`, and provider failure returns the deterministic fallback.
- Repeat the live smoke. Record `source: 'llm'` if it succeeds. If the configured provider is externally unavailable, record the sanitized failure category and keep this acceptance item explicitly blocked rather than claiming success.

### R2 — Timeline keys are nondeterministic when a lifecycle ID is absent (medium)

- `frontend/lib/case-detail-state.ts:150` uses `Math.random()` when `evt.id` is missing, although `LifecycleEventRecord.id` is optional in the frontend contract.
- Calling `deriveCaseTimeline` twice with the same persisted data produces different keys. This violates deterministic derivation, can cause avoidable React remounts, and is not covered by the current ordering regression.
- Build the fallback key from persisted fields plus the stable lifecycle-array index. Add a regression that omits event IDs, derives twice, and asserts deep equality including keys.

### R3 — Timeline details invent a technician identity (medium)

- `frontend/lib/case-detail-state.ts:141`, `:160-161`, `:172`, and `:181` substitute the literal `technician` when a confirmation or lifecycle actor is absent.
- DLK-M3-030 requires the view to render only persisted values and expressly forbids generating a hardcoded Engineer/Technician identity. The current identity test checks only `deriveCaseOwner`, so it misses the timeline output.
- Use `Not recorded` or omit the actor clause when the persisted actor is blank. Extend the production-helper regression across confirmation, recovery action, recovery verification, and recurrence entries, and assert that no hardcoded identity is generated.

## Verified strengths

- `/cases/[id]` performs the authoritative GET in the page and exposes mutually exclusive loading, error/retry, and loaded states.
- Retry uses `casesApi.getCase` only; the page does not replay a mutation.
- `CaseDetails` receives the durable response, uses the actual case ID for diagnosis/report links, shows persisted state, and no longer renders Similar Cases.
- The production case-detail helper is shared with the Node regression.
- All 39 frontend state regressions passed: case detail 7, image upload 7, reports 9, and diagnostic workflow 16.
- Full `npm run lint` completed with zero findings.
- `npm run build` passed TypeScript and generated all expected routes.
- Task validation returned `VALID`; committed whitespace inspection passed.
- Independent focused AI-summary verification passed ten tests, and the full backend verification passed 491 tests with 42 warnings using repository-local pytest base temp directories.
- No new dependency, migration, diagnostic-weight change, Similar Cases backend, or raw image asset was introduced by the reviewed commit.

## Final status

No further correction is required for DLK-M3-030. The reviewed commits remain local on `backend-database`; publication and integration require the user's separate instruction.
