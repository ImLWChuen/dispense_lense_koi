---
task_id: DLK-M3-004
reviewed_commit: 2459c0a0e2345b2073efe0e51670639b87c0eebb
decision: changes_requested
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-004

## Decision

Changes requested: a bounded API-contract and verification closeout. The initial diagnosis endpoint is structurally sound and no blocking defect was found in the route-to-engine integration during static review and local test replay. The remaining issues are that the committed tests do not fully prove several explicit acceptance requirements, and the written API contract contains examples that do not match the implemented endpoint.

Git verification was subsequently completed in the shared repository. The reviewed implementation is commit `2459c0a0e2345b2073efe0e51670639b87c0eebb` (`feat(api): expose initial diagnosis through FastAPI`), whose sole parent is the reconciled baseline `b953ebf5b9aaee04c3e52cac30b9cb7b9871a429`. The commit changes 22 files with 1,208 insertions and 63 deletions; every changed path falls within the task packet's allowed paths. After `git fetch origin --prune`, local `backend-database` is exactly one commit ahead of `origin/backend-database` (`0 1` from remote to local), and no fetched remote branch contains the reviewed commit. This verifies that the implementation commit has not been pushed to a current remote branch. The only uncommitted paths at verification time are this reviewer-added review record and the corresponding queue update, so neither belongs to the implementation commit.

The exact commit check `git diff --check b953ebf5b9aaee04c3e52cac30b9cb7b9871a429 2459c0a0e2345b2073efe0e51670639b87c0eebb` reports one trailing blank line at the end of `.agents/handoff/tasks/DLK-M3-004-initial-diagnosis-api.md`. This is a non-product formatting issue, but it means the implementation report's claim that the committed diff check was completely clean could not be reproduced.

## Acceptance evidence

- `backend/app/api/diagnoses.py` exposes synchronous `POST /api/v1/diagnoses` through the existing `/api/v1` router and returns the existing `DiagnosisResult` response model.
- The route obtains a fresh `DiagnosticEngine` through an injectable FastAPI dependency and performs a single `engine.diagnose(...)` call. No shared mutable case cache or persistence layer is introduced.
- `InitialDiagnosisRequest` forbids extra top-level fields, validates supplied defect codes through the existing knowledge loader, rejects requests with neither a non-blank description nor observations, and adapts accepted input into the existing domain `DiagnosisRequest` without accepting caller-owned case/revision history.
- A known defect code without description or observations is rejected with HTTP 422 in direct review replay. Observations without a description are accepted, as required.
- The unidentifiable-input path remains an ordinary HTTP 200 engine result with nullable defect/analysis fields and a warning instead of being converted into a transport error.
- Unexpected engine exceptions are converted to a generic HTTP 500 response. The response does not expose the injected exception text, credentials, stack trace, or filesystem details.
- Canonical backend imports use `app.*`; package data includes `app.knowledge/*.json`, supporting standalone backend installation rather than repository-root import hacks.
- Health routing remains present and separate from the diagnosis route.
- The current snapshot's full backend suite was independently replayed during this review and passes: `24 passed in 0.46s`.
- The API documentation correctly labels cause scores as evidence-support scores rather than calibrated probabilities and clearly states that this endpoint is initial-only and stateless.
- Git metadata identifies the exact reviewed commit and its baseline, confirms the implementation is one atomic local commit, and confirms all 22 changed paths are within the authorized task scope.

## Findings

### R1 - P2: Make the API specification match the executable contract

`docs/api/api-spec.md` does not currently describe the implemented endpoint precisely enough to satisfy the task's documentation acceptance criterion.

Concrete mismatches:

- The implemented and tested 500 response is:
  `{"detail": "An unexpected error occurred during diagnosis evaluation."}`
  while the API specification documents:
  `{"detail": "An internal diagnostic error occurred."}`
  and the task implementation report also claims the latter string. One canonical response must be chosen and used consistently in route, tests, task report, and API specification.
- The documented custom HTTP 422 example uses a plain string detail (`"At least one observation or a non-empty problem description must be provided."`). The actual Pydantic/FastAPI response for this model-level validation is a structured `detail` array and uses the implemented message `"Insufficient evidence input: provide a non-empty description or at least one observation."` The error section should show an actual captured response or explicitly mark simplified examples as illustrative.
- The documented `Observation` request table omits fields that the endpoint really accepts through the reused domain model, notably `id` and `timestamp`. Because the task deliberately authorized `list[Observation]`, the documentation should describe the actual accepted schema rather than a narrower implied transport shape.
- The section labelled **Real Execution Example** cannot be a literal untouched execution result as written: the response uses the same UUID for `case_id` and supporting `observation_id`, while the request does not provide an observation ID and the engine independently generates the transient case ID and observation ID. If UUIDs were normalized/redacted for readability, state that explicitly; otherwise regenerate the example directly from the endpoint and paste the actual output.

This is not a request to redesign the transport or engine. Correct the documentation/report to the behavior already implemented, or deliberately change the response text and tests together if the planner chooses the documented wording as canonical.

### R2 - P2: Complete the acceptance tests required by the task packet

The current integration suite is useful but does not fully execute the explicit verification requested in DLK-M3-004.

- `test_defect_code_alone_is_insufficient_evidence` uses `D01_BRIDGING`, which is not a known defect code. The test therefore passes through the **unknown defect** validation branch and does not prove the separate requirement that a **valid known defect code alone** is still insufficient evidence. Use an existing code such as `D01_TOO_LITTLE` for this test and keep the unknown-code test separately.
- `test_independent_submissions_generate_unique_case_ids_and_do_not_leak_state` verifies only different case IDs and `revision_number == 1`. The task explicitly requires proving that identical submissions do not share observations or revisions. Add assertions against independently generated observation IDs / revision objects or otherwise demonstrate that state from one run cannot appear in the other.
- `test_scores_and_evidence_match_direct_engine_call` verifies cause identity, score, conclusion, and only the **count** of supporting evidence. The task explicitly requires returned **evidence and scores** to match a direct engine call while excluding generated IDs/timestamps. Normalize the two result objects by removing nondeterministic IDs/timestamps, then compare the relevant evidence relations, strengths, sources, explanations/contributions, score breakdowns, and other preserved domain state. This is particularly important because preserving evidence/provenance without transport reinterpretation is a core requirement of this task.

The implementation currently appears to satisfy these behaviors, so this finding is a verification gap rather than evidence that the endpoint is functionally wrong.

## Non-blocking architectural note

Because the planner-mandated transport directly reuses the domain `Observation` model, an external caller can currently supply provenance-bearing fields such as `source`, `statement_type`, `id`, and `timestamp`; review replay confirmed that values such as `source="SYSTEM"` and `statement_type="AI_INFERENCE"` are accepted and propagated into diagnostic evidence. This follows the authorized DLK-M3-004 contract, so it is not assigned as an implementation defect here. Before this endpoint becomes a production trust boundary, the team should decide whether user-facing transport should be allowed to assert system/AI/historical provenance or whether those fields must be server-owned.

## Follow-up

Create a bounded DLK-M3-005 correction task before starting database persistence work:

1. Align `docs/api/api-spec.md`, the DLK-M3-004 implementation report, and executable error responses/examples.
2. Add the missing known-defect-only validation test.
3. Strengthen state-isolation and direct-engine parity tests to cover actual evidence/state rather than counts only.
4. Re-run focused integration tests and the full backend suite; record actual counts/warnings.
5. Reassess DLK-M3-004 for acceptance after the correction. No diagnostic algorithm, knowledge rules, database design, frontend, dependency, or LLM changes are required for this closeout.

The next persistence milestone should remain gated on accepting this correction so Member 1 and later backend tasks build against one accurate, executable initial-diagnosis contract.
