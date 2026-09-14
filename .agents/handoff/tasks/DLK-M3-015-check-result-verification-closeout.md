---
task_id: DLK-M3-015
title: Make check-result rollback and state-preservation verification conclusive
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-014]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-015: Check-result verification closeout

## Objective

Close R1 in the DLK-M3-014 review through bounded test corrections. Prove that the API rollback scenario reaches the intended injected failure after real writes, and that rollback/rejection preserves complete prior state. No production-code correction is currently requested.

## Current evidence

- Baseline: `0e220344f9e96fa40a5443db9f72e9cfa5fb5ce5` on `backend-database`.
- Read `.agents/handoff/reviews/DLK-M3-014-review.md` and the DLK-M3-014 packet. Its implementation is the required dependency; its acceptance is not required because this task corrects it.
- PENDING and IN_PROGRESS rejection is already implemented and accepted within the prior review. Preserve it.
- The API rollback test sets hook_called before assertions inside before_commit. The endpoint can catch an AssertionError and return the expected sanitized 500, allowing a false-positive test.
- The API/repository rollback tests and unfinished-state regression compare counts and revision numbers, leaving the required complete prior-state preservation unproven.
- Gemini previously reported 208 backend tests passing. This is historical implementer evidence, not a result for this correction.
- Pending queue and review artifacts belong to this handoff and must be preserved and included in the implementation commit.

## Requirements

### Observable fault evidence

- Preserve real API append/flush behavior and the test-only before_commit failure seam.
- In the hook, capture detached, immutable values proving that the target transaction contains the expected check event, generated observations at the new revision, and complete new revision snapshot. Do not retain live ORM objects as evidence.
- Set a separate fault_reached marker immediately before raising the specific intended synthetic RuntimeError.
- After client.post returns, assert the captured evidence and fault_reached marker outside the endpoint's exception handling. A hook assertion failure or an unrelated internal exception must not count as reaching the deliberate fault.
- Retain sanitized HTTP 500 assertions and fresh-independent-session rollback checks. Always remove event listeners in finally, including on assertion failure.
- Keep the repository test's specific expected RuntimeError assertion; ensure its real pending-write proof and natural rollback remain intact. Do not manually roll back as the mechanism under test.

### Complete preservation comparison

- Add a small test-local snapshot helper if useful. Capture scalar values from the case row, all observations, question answers, check results, and every analysis revision including full result_snapshot JSON and metadata.
- Use deterministic ordering and detached/deep-copied values. Query stored records directly without rerunning diagnosis. Compare full values, not just counts or domain reconstruction that could omit stored fields.
- Capture the target and unrelated control snapshots before each rollback scenario and compare with snapshots from a fresh independent session afterward.
- Strengthen both PENDING and IN_PROGRESS API regressions to compare the complete baseline with the state after the rejected request.
- Use nonempty prior question/check histories for the rollback target, and representative existing data for the control case, so preservation is not established only for empty lists. Use existing public engine/repository/API operations to establish these baselines. Derive expected_revision and the attempted next revision from the baseline rather than hard-coding revision 2.
- All attempted new check/observation/revision records must be absent after rollback, while all prior snapshots and histories remain exactly unchanged.

### Test sensitivity

- Demonstrate that the API proof fails when its expected pending-write evidence is deliberately made incorrect even though the endpoint still returns 500. Use a temporary local test-only perturbation or a focused assertion-helper test; restore all intentional perturbations before final verification and commit.
- Demonstrate that snapshot comparison detects a changed value inside a copied prior result_snapshot while row counts/revision numbers are unchanged. This may be a small connection-free helper check; no destructive database mutation is needed.
- Record actual outcomes and distinguish temporary expected failures from final passing results.

## Interfaces and data contracts

No API, engine, database, migration, dependency, or production transaction contract changes. Test helpers may return plain dictionaries/lists of persisted scalar values for exact comparisons. Preserve the established PostgreSQL destination guard and case-specific cleanup.

## Allowed paths

- `backend/tests/integration/test_check_result_api.py`
- `backend/tests/integration/test_persistence.py`
- A small test-only snapshot helper under `backend/tests/` if needed by both modules; avoid a generic framework.
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-014-review.md` (include unchanged)
- `.agents/handoff/tasks/DLK-M3-014-check-result-closeout.md` (narrow report accuracy corrections only)
- `.agents/handoff/tasks/DLK-M3-015-check-result-verification-closeout.md`

## Prohibited scope

No production-code edits, schema/migration changes, new dependencies, diagnostic semantic changes, frontend work, next-feature work, production failure switches, weakened assertions, database resets, or remote Git operations. Do not rewrite prior review decisions or mark this correction accepted yourself.

## Implementation guidance

1. Confirm the branch, baseline, clean application files, pending handoff artifacts, and DLK-M3-015 as the only ready task.
2. Read the two affected test modules and their fixtures, production transaction boundaries, and persistence models before defining snapshot coverage.
3. Repair the API hook proof and add complete baseline comparisons to both rollback tests and both unfinished-state cases.
4. Run the sensitivity checks, restore temporary perturbations, and run final focused and full verification.
5. Complete the report, set this task and queue to implemented, inspect the staged diff, and commit locally.

## Acceptance criteria

- [x] The API test asserts immutable pending-write evidence outside request handling.
- [x] The intended fault marker is checked outside request handling; unrelated exceptions cannot satisfy the proof.
- [x] Real pending check, generated observations, and new revision exist before the deliberate fault.
- [x] API and repository transaction boundaries perform rollback naturally.
- [x] Independent sessions confirm exact preservation of full target and control state, including nonempty histories and complete stored revision snapshots.
- [x] Both unfinished states return 422 and preserve full prior stored state.
- [x] Incorrect pending evidence makes verification fail even with HTTP 500.
- [x] Snapshot comparison detects changed contents without relying on changed counts.
- [x] Temporary perturbations and event listeners are removed.
- [x] Focused and full backend verification pass against approved local PostgreSQL.
- [x] No production code or out-of-scope files change; no remote operation occurs.

## Verification

Use the existing verified local PostgreSQL test destination. Do not print credentials, bypass the destination guard, or substitute SQLite. From `backend/`:

1. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_check_result_api.py`
2. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_persistence.py`
3. Run any new focused test-helper sensitivity tests explicitly.
4. `.\.venv\Scripts\python.exe -m pytest -q`

From repository root:

5. `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-015-check-result-verification-closeout.md`
6. `git diff --check`
7. Inspect status, staged file names and complete staged diff. If database verification cannot run, report blocked with the observed cause; do not claim success.

## Planner decision boundaries

Return before production fixes, database/schema changes, safety-policy changes, dependencies, diagnostic changes, or scope expansion. If stronger tests uncover a real production failure, retain the evidence and report it rather than weakening the tests or fixing production code in this packet.

## Git instructions

Create one atomic local commit after successful verification. Include pending DLK-M3-014 review, queue and this completed packet with the test corrections. Preserve DLK-M3-013 and DLK-M3-014 review history. Set DLK-M3-015 to implemented, not accepted. Do not push, merge, rebase, create/update a PR, or modify main.

Proposed commit: `test(api): prove check rollback and full state preservation`

## Implementation report

### Summary

Successfully implemented DLK-M3-015 test corrections closing R1 from DLK-M3-014 review:
1. Implemented a test-local snapshot capture helper `backend/tests/case_snapshot_helper.py` (`capture_complete_case_state`) that queries raw database tables directly, deep-copies JSON snapshots, and returns an immutable state dictionary including the case row, deterministically ordered observations, question answers, check results, and analysis revision records with full result snapshots.
2. Hardened `test_induced_persistence_failure_returns_sanitized_500_and_rolls_back` in `backend/tests/integration/test_check_result_api.py`:
   - Advanced both target and control cases to Revision 2 with prior question answers (nonempty histories).
   - Captured complete baseline states before the test request.
   - Dynamically derived expected and attempted revision numbers.
   - Captured detached immutable evidence (check result, observations, revision snapshot) in the `before_commit` hook without retaining live ORM objects.
   - Set a dedicated `fault_reached = True` flag immediately before raising `RuntimeError`.
   - Asserted the captured pending evidence and `fault_reached` marker *outside* `client.post` (outside route exception handlers), preventing any swallowed `AssertionError`.
   - Asserted sanitized HTTP 500 response without sensitive paths.
   - In a fresh independent session, confirmed that target and control cases match their complete prior baseline states (`target_after == target_baseline` and `control_after == control_baseline`).
3. Hardened `test_unfinished_execution_status_rejected_with_422_and_no_mutation` in `backend/tests/integration/test_check_result_api.py` for both PENDING and IN_PROGRESS states:
   - Established nonempty prior answer history and Revision 2 on the target case.
   - Captured complete baseline state before the rejected request.
   - Verified 422 rejection and proved that complete case state in an independent session remains 100% identical to baseline.
4. Hardened `test_append_check_result_revision_rollback_on_failure` in `backend/tests/integration/test_persistence.py`:
   - Advanced target and control cases to Revision 2 via question answers.
   - Dynamically derived baseline and attempted revision numbers.
   - Captured detached pending evidence in `before_commit` and asserted `fault_reached` and pending records outside repository invocation.
   - Verified that complete target and control baselines are preserved identically after natural transaction rollback.
5. Added test sensitivity checks:
   - Added `test_snapshot_helper_detects_nested_snapshot_mutation_with_identical_counts` demonstrating that `capture_complete_case_state` detects nested changes within `result_snapshot` even when row counts and revision numbers are unchanged.
   - Executed a temporary local perturbation on `check_id` assertion in `test_induced_persistence_failure_returns_sanitized_500_and_rolls_back`, demonstrating that the test fails outside request handling despite HTTP 500 being returned, and restored the original assertion.
6. Absolutely no production code was modified. Strictly test-only changes.

### Files changed

- `backend/tests/case_snapshot_helper.py` (new test helper): `capture_complete_case_state` capturing detached, deterministic scalar fields, observations, answers, check results, and revision snapshot JSON.
- `backend/tests/integration/test_check_result_api.py`: Hardened API rollback and unfinished execution status tests with nonempty histories, outside assertion of immutable pending evidence and fault marker, complete baseline comparisons, and snapshot helper sensitivity test.
- `backend/tests/integration/test_persistence.py`: Hardened repository rollback test with nonempty baselines, outside assertion of immutable pending evidence and fault marker, and full state preservation comparison.
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-015 status to `implemented`.
- `.agents/handoff/tasks/DLK-M3-015-check-result-verification-closeout.md`: Updated acceptance criteria and implementation report.

### Decisions made

- Isolated assertion logic from SQLAlchemy session hooks: The `before_commit` listener records immutable primitive dictionaries and flags `fault_reached = True` immediately before raising the simulated fault. All assertions occur outside the `client.post` call, guaranteeing that FastAPI's outer exception handler cannot convert hook `AssertionError`s into false-positive HTTP 500 passes.
- Direct database query for snapshots: `capture_complete_case_state` queries `CaseModel`, `ObservationModel`, `QuestionAnswerModel`, `CaseCheckResultModel`, and `AnalysisRevisionModel` directly using `populate_existing=True` and deep-copies `result_snapshot` to avoid ORM caching or domain mapper omissions.
- Dynamic revision derivation: `baseline_rev` is derived from `target_baseline["analysis_revisions"][-1]["revision_number"]` and `attempted_rev = baseline_rev + 1`, eliminating hard-coded revision 2 expectations.

### Verification results

1. Sensitivity Verification:
   - `pytest -q backend/tests/integration/test_check_result_api.py -k test_snapshot_helper_detects_nested_snapshot_mutation_with_identical_counts`: PASSED (demonstrates snapshot helper detects nested dict mutation with identical row counts).
   - Temporary perturbation test: Intentionally modified `check_id == "ACT01"` to `"INCORRECT_CHECK_ID"` in outside assertion. Observed: HTTP 500 was logged by route handler, but test failed with `AssertionError: assert 'ACT01' == 'INCORRECT_CHECK_ID'`, proving the test cannot be satisfied by swallowed exceptions. Restored to `"ACT01"`.
2. Focused Test Suites against PostgreSQL 16:
   - `pytest -q backend/tests/integration/test_check_result_api.py`: 23 passed in 4.44s.
   - `pytest -q backend/tests/integration/test_persistence.py`: 28 passed in 4.39s.
3. Full Backend Suite against PostgreSQL 16:
   - `pytest -q backend`: 209 passed, 12 warnings in 12.19s.
4. Task Validation Script:
   - `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-015-check-result-verification-closeout.md` passed with 0 errors.

### Limitations and follow-up

- All R1 concerns from the DLK-M3-014 review have been addressed and verified with conclusive evidence.
- The task is ready for review.

### Proposed commit message

`test(api): prove check rollback and full state preservation`
