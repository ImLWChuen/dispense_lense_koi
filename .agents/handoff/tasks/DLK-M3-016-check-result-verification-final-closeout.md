---
task_id: DLK-M3-016
title: Finalize check-result rollback and exact-state verification
status: implemented
created_by: planner
assigned_to: implementer
depends_on: [DLK-M3-015]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-016: Final check-result verification closeout

## Objective

Close the two remaining **test-only** findings from the DLK-M3-015 review so the DLK-M3-013 → 014 → 015 correction chain can be accepted.

No production-code defect is currently identified and no production-code change is authorized.

This task must:

1. prove rollback preserves a **nonempty existing check-result history**, not only question-answer history; and
2. make the complete-state snapshot helper preserve **exact stored scalar values** and capture the **complete pending revision snapshot** during rollback fault injection.

## Current evidence

- DLK-M3-015 was implemented at `9ad094cfa3b56e3042996238ce4acc0752f9f98c` and reviewed with `changes_requested`.
- Reviewer confirmed the swallowed-assertion issue is resolved and no production-code defect is currently identified.
- Remaining findings are test-only: nonempty prior check history is not exercised, optional text values are not preserved exactly in snapshots, and pending rollback evidence does not capture the complete revision `result_snapshot`.
- The existing full-state helper, outside-request fault markers, independent-session verification, and PENDING/IN_PROGRESS rejection tests must be preserved.

## Review basis

DLK-M3-015 was reviewed at commit:

`9ad094cfa3b56e3042996238ce4acc0752f9f98c`

The review returned `changes_requested` with two bounded verification gaps.

### R1 - rollback baselines do not contain prior check history

The API and repository rollback targets are advanced using a question answer only. Their `check_results` baseline is empty. The test therefore proves removal of a failed first check, but cannot detect accidental mutation/corruption of an already persisted check event during a later failed check submission.

### R2 - snapshot helper normalizes distinct stored values

`capture_complete_case_state()` currently uses truthiness expressions such as:

- `str(value) if value else None`
- `description or ""`

for several stored optional text fields. This makes `""` and SQL `NULL` observationally identical even though the task requires exact stored-state preservation.

The rollback hooks also currently retain only revision-snapshot presence/keys in places rather than the complete pending `result_snapshot` JSON.

## Requirements

### 1. Seed nonempty prior check history in both rollback targets

Strengthen both:

- the API rollback scenario in `backend/tests/integration/test_check_result_api.py`; and
- the repository rollback scenario in `backend/tests/integration/test_persistence.py`.

Before capturing each rollback target baseline:

1. create the durable target case;
2. persist at least one valid prior question answer through the existing accepted workflow;
3. persist at least one valid prior check result through the existing accepted workflow;
4. reload/capture the baseline from an independent session;
5. assert both `question_answers` and `check_results` are nonempty;
6. derive the current and attempted next revision numbers dynamically from the captured baseline;
7. attempt a **subsequent** evidence-producing check result and inject the rollback fault after writes/flushes but before commit.

The prior check must be created through existing public/production operations. Do not insert synthetic rows directly merely to satisfy the baseline.

After rollback, compare the full target baseline captured before the failed subsequent check with a fresh independent-session snapshot. The previously stored check event must remain exactly unchanged.

Retain the unrelated control-case full-state comparison.

### 2. Preserve exact stored scalar values in snapshot helper

Update `backend/tests/case_snapshot_helper.py` so snapshot capture preserves stored scalar values exactly.

For optional text/database fields, do **not** use truthiness to normalize `""` into `None`.

Examples include, where present in the helper/model:

- `material`
- `method`
- `defect_code`
- `defect_name`
- observation `original_text`
- question-answer `answer_text`
- check-result `finding_details`
- check-result `outcome`
- any other optional stored text field captured by this helper

Use exact stored values and only transform types when necessary for deterministic comparison, such as:

- UUID -> string
- enum/database enum -> stable string
- datetime -> deterministic ISO representation
- JSON -> deep copy

Do not collapse distinct persisted values.

### 3. Add exact-value sensitivity coverage

Add a focused helper-level test proving the snapshot mechanism distinguishes:

- a supported field stored as `""`; and
- the same field stored as `None`.

The test must demonstrate that the resulting captured snapshots differ even when row counts/revision numbers are unchanged.

Prefer a real model/database-backed check if the existing test fixtures make that straightforward. A tightly scoped helper-level unit check is acceptable only if it exercises the same normalization logic used by `capture_complete_case_state()`.

Retain the existing nested `result_snapshot` mutation sensitivity test.

### 4. Capture complete pending revision snapshot in both rollback hooks

In both the API and repository rollback fault hooks, capture detached immutable evidence for the pending analysis revision including the **entire** `result_snapshot` JSON payload.

Do not reduce pending revision evidence to only:

- `has_snapshot`;
- `snapshot_keys`;
- shape/presence metadata.

Use a deep copy or equivalent detached immutable structure.

After the request/repository call returns/raises, outside handled production exception boundaries, assert:

- the intended fault was reached;
- pending check history existed;
- pending generated observations existed;
- pending analysis revision existed;
- pending `result_snapshot` was nonempty/complete and contains the expected revision semantics;
- the pending revision number equals the dynamically derived attempted revision.

Do not retain live ORM instances as proof.

### 5. Preserve all already-resolved protections

Do not weaken or remove:

- outside-request assertion of pending-write evidence;
- the dedicated `fault_reached` marker;
- natural production rollback behavior;
- fresh independent-session rollback verification;
- unrelated control-case preservation comparison;
- `PENDING` / `IN_PROGRESS` 422 rejection tests;
- full-state comparison for unfinished-state rejection;
- temporary perturbation/sensitivity evidence already established by DLK-M3-015.

## Implementation guidance

1. Read DLK-M3-015 review, the existing snapshot helper, and both rollback tests before editing.
2. Seed one accepted prior question answer and one accepted prior check result for each rollback target using existing production/public operations.
3. Correct exact scalar capture in the snapshot helper and add the empty-string-vs-NULL sensitivity check.
4. Capture the full detached pending revision JSON in both rollback hooks and assert it outside handled exception boundaries.
5. Run the required sensitivity demonstrations, restore temporary perturbations, then run focused and full PostgreSQL verification.
6. Complete the implementation report, inspect the staged diff, and create one atomic local commit.

## Interfaces and data contracts

No API, domain, engine, ORM, database, migration, dependency, or transaction contract changes.

This is strictly a verification correction.

## Allowed paths

- `backend/tests/case_snapshot_helper.py`
- `backend/tests/integration/test_check_result_api.py`
- `backend/tests/integration/test_persistence.py`
- a small existing/new test-only helper under `backend/tests/` only if required for exact-value sensitivity
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-015-review.md` (include unchanged)
- `.agents/handoff/tasks/DLK-M3-015-check-result-verification-closeout.md` only for narrow report-accuracy corrections if required
- `.agents/handoff/tasks/DLK-M3-016-check-result-verification-final-closeout.md`

Return to the planner before editing outside this scope.

## Prohibited scope

No production-code edits.

Do not change:

- API routes or schemas;
- diagnostic engine/handler behavior;
- check mappings/evidence rules/scoring;
- ORM/database schema;
- Alembic migrations;
- dependencies;
- PostgreSQL safety policy;
- transaction implementation;
- cause confirmation or issue-resolution behavior.

Do not start the next product milestone.

## Acceptance criteria

### Prior history preservation

- [x] API rollback target has nonempty prior `question_answers` before the failed submission.
- [x] API rollback target has nonempty prior `check_results` before the failed submission.
- [x] Repository rollback target has nonempty prior `question_answers` before the failed submission.
- [x] Repository rollback target has nonempty prior `check_results` before the failed submission.
- [x] Prior check result is created through existing accepted production/public operations.
- [x] Attempted revision is derived dynamically from the captured baseline.
- [x] After rollback, complete target state exactly equals the pre-failure baseline.
- [x] Previously persisted check history remains exactly unchanged.
- [x] Unrelated control case remains exactly unchanged.

### Exact snapshot preservation

- [x] Snapshot helper preserves `""` and `None` as distinct stored values.
- [x] No captured optional text field uses truthiness to collapse distinct persisted values.
- [x] JSON values remain deep-copied/detached.
- [x] Deterministic ordering remains intact.
- [x] Focused sensitivity test proves `""` and `None` produce different snapshots.
- [x] Existing nested result-snapshot sensitivity remains passing.

### Pending revision proof

- [x] API rollback hook captures complete detached pending `result_snapshot` JSON.
- [x] Repository rollback hook captures complete detached pending `result_snapshot` JSON.
- [x] Evidence assertions occur outside production exception handling.
- [x] `fault_reached` is asserted outside the request/repository call.
- [x] Pending check, observation(s), revision number, and complete result snapshot are all asserted.
- [x] Fresh independent sessions prove all attempted new rows are absent after rollback.

### Regression

- [x] PENDING and IN_PROGRESS remain rejected with 422 and no mutation.
- [x] Check-result API happy path remains passing.
- [x] Supporting checks do not auto-confirm causes.
- [x] Check results do not auto-resolve issues.
- [x] Question-answer workflow remains passing.
- [x] Durable case/diagnosis/health APIs remain passing.
- [x] Persistence-safety tests remain passing.
- [x] Full backend suite passes against verified local PostgreSQL.
- [x] No production file changed.
- [x] Only authorized files changed.
- [x] No remote Git operation occurs.

## Verification

Use the accepted verified local PostgreSQL test database.

From `backend/`, run at minimum:

1. Focused snapshot-helper sensitivity tests.
2. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_check_result_api.py`
3. `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_persistence.py`
4. Existing semantic/check-result focused suites.
5. Existing question-answer API/revision suites.
6. Durable case + diagnosis + health API suites.
7. Persistence-safety suite.
8. `.\.venv\Scripts\python.exe -m pytest -q`

From repository root:

9. `backend/.venv/Scripts/python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-016-check-result-verification-final-closeout.md`
10. `git diff --check`
11. Inspect `git status`, staged file names, and full staged diff before commit.

If real PostgreSQL verification cannot run, mark the task `blocked`; do not substitute SQLite for the required rollback proof.

## Test sensitivity evidence

Before final verification, demonstrate both of the following and restore any deliberate perturbation:

1. altering expected pending revision snapshot content causes the rollback proof to fail outside production exception handling;
2. changing a copied baseline optional field from `""` to `None` (or vice versa) causes exact snapshot comparison to fail while counts/revision numbers remain unchanged.

Record the temporary expected failures separately from final passing results.

## Planner decision boundaries

Return to the planner before:

- touching production code;
- changing DB schema/migrations;
- weakening exact-value comparison;
- removing nonempty prior check history;
- replacing full pending result-snapshot capture with shape-only evidence;
- adding production failure-injection hooks;
- starting cause-confirmation work.

## Git instructions

After all criteria pass:

- complete this task's implementation report;
- set DLK-M3-016 and `QUEUE.md` to `implemented`;
- inspect staged names and full staged diff;
- create exactly one atomic local commit.

Proposed commit message:

`test(api): finalize check rollback verification`

Do not push, merge, rebase, create/update a PR, or modify `main`.

## Implementation report

Complete before the local commit.

### Summary

Successfully implemented and verified all DLK-M3-016 test-only requirements:
1. Seeded both prior question-answer (Q01) and prior check-result (ACT02) history into the rollback target cases using existing public operations, and asserted nonempty prior history (`check_results` and `question_answers`) before subsequent check failure injection.
2. Refactored `backend/tests/case_snapshot_helper.py` to preserve exact stored scalar values without truthiness normalization, ensuring `""` and `None` remain distinct across all optional text fields.
3. Added a dedicated PostgreSQL-backed exact-value sensitivity test (`test_snapshot_helper_distinguishes_empty_string_and_none_for_optional_fields`) proving that `""` and `None` are distinguished and that changing `""` to `None` in a baseline copy causes exact state comparison to fail with identical row counts and revisions.
4. Upgraded both API (`test_check_result_api.py`) and repository (`test_persistence.py`) rollback fault injection hooks to capture complete detached `result_snapshot` JSON payloads, asserting full snapshot contents (`defect`, `ranked_causes`) outside production exception handling.
5. Preserved all prior protections: outside-request assertion of immutable pending evidence and fault marker, natural transaction rollback, fresh independent-session verification, control case baseline comparison, and 422 rejection for PENDING/IN_PROGRESS.
6. Strictly test-only: 0 production lines modified.

### Files changed

- `backend/tests/case_snapshot_helper.py`: Removed truthiness collapsing (`if val else None` / `or ""`) across `CaseModel`, `ObservationModel`, `QuestionAnswerModel`, `CaseCheckResultModel`, and `AnalysisRevisionModel`. Preserves exact stored strings (`""` remains `""`, `None` remains `None`).
- `backend/tests/integration/test_check_result_api.py`:
  - Added prior check result submission (ACT02) advancing target and control cases to Revision 3 before subsequent check failure.
  - Dynamically derived `baseline_rev` (3) and `attempted_rev` (4).
  - Captured and deep-copied complete pending `result_snapshot` in `before_commit` hook.
  - Added outside assertion verifying pending `result_snapshot` JSON contains `defect` and `ranked_causes`.
  - Added `test_snapshot_helper_distinguishes_empty_string_and_none_for_optional_fields` testing real PostgreSQL persistence and retrieval of `""` vs `None`.
- `backend/tests/integration/test_persistence.py`:
  - Added prior check result revision (ACT02) advancing target and control cases to Revision 3.
  - Dynamically derived `baseline_rev` (3) and `attempted_rev` (4).
  - Captured complete detached `result_snapshot` in `before_commit` hook and asserted it outside the repository call.
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-016 status to `implemented`.
- `.agents/handoff/tasks/DLK-M3-016-check-result-verification-final-closeout.md`: Recorded complete implementation report and set status to `implemented`.

### Prior check-history baseline proof

In both `test_check_result_api.py` and `test_persistence.py`:
- Target cases are created (Rev 1), answered with Q01 (Rev 2), and submitted with check ACT02 (Rev 3).
- Control cases are similarly advanced to Rev 3 with Q01 and ACT02.
- Before failure injection, independent-session baselines confirm:
  `assert len(target_baseline["analysis_revisions"]) >= 3`
  `assert len(target_baseline["question_answers"]) >= 1`
  `assert len(target_baseline["check_results"]) >= 1`
- The subsequent check attempt (ACT01) targets dynamically-derived `attempted_rev = baseline_rev + 1` (Rev 4).
- After rollback, an independent session verifies that all Rev 4 records are absent, `target_after == target_baseline`, and the previously persisted check ACT02 remains intact (`target_after["check_results"][0]["check_id"] == "ACT02"`).

### Exact-value snapshot correction

In `backend/tests/case_snapshot_helper.py`:
- All optional text expressions changed from `str(x) if x else None` or `x or ""` to `str(x) if x is not None else None`.
- If a column contains `""`, `x is not None` is `True` and `str("")` evaluates to `""`.
- If a column contains `None` (SQL NULL), `x is not None` is `False` and returns `None`.
- Deep copies are preserved for `machine_context` and `result_snapshot`.

### Complete pending revision proof

In both rollback hooks (`before_commit` listeners):
- Captured `rev_data["result_snapshot"] = copy.deepcopy(revs[0].result_snapshot)`.
- Asserted outside request / repository execution:
  - `assert fault_reached is True`
  - `pending_snapshot = captured_pending_evidence["analysis_revision"]["result_snapshot"]`
  - `assert isinstance(pending_snapshot, dict) and len(pending_snapshot) > 0`
  - `assert pending_snapshot["defect"] == "D03_INCONSISTENT_SIZE"`
  - `assert any(c["cause_id"] == "nozzle_restriction" for c in pending_snapshot["ranked_causes"])`

### Sensitivity checks

1. **Pending snapshot content perturbation:**
   - Temporarily changed `assert pending_snapshot["defect"] == "D03_INCONSISTENT_SIZE"` to `"WRONG_DEFECT_TRIGGERING_OUTSIDE_FAILURE"`.
   - Result: Although route handler logged and returned HTTP 500, test failed outside `client.post` with:
     `AssertionError: assert 'D03_INCONSISTENT_SIZE' == 'WRONG_DEFECT_TRIGGERING_OUTSIDE_FAILURE'`
   - Restored to `"D03_INCONSISTENT_SIZE"`, which passed cleanly.
2. **Empty-string vs NULL perturbation:**
   - In `test_snapshot_helper_distinguishes_empty_string_and_none_for_optional_fields`, temporarily asserted `assert snapshot_empty == copied` where `copied["case"]["material"] = None`.
   - Result: Test failed with:
     `AssertionError: assert {'case': {..., 'material': ''}} == {'case': {..., 'material': None}}`
   - Restored to `assert snapshot_empty != copied`, which passed cleanly.

### Verification results

All suites executed against verified local PostgreSQL 16 Alpine container:
1. `pytest -q backend/tests/integration/test_check_result_api.py -k test_snapshot_helper`: **2 passed**
2. `pytest -q backend/tests/integration/test_check_result_api.py`: **24 passed**
3. `pytest -q backend/tests/integration/test_persistence.py`: **28 passed**
4. `pytest -q backend/tests/integration/test_check_result_diagnosis_revision.py backend/tests/unit/test_check_result_handler.py backend/tests/unit/test_semantic_verification.py`: **54 passed**
5. `pytest -q backend/tests/integration/test_question_answer_api.py backend/tests/integration/test_question_answer_diagnosis_revision.py backend/tests/unit/test_question_answer_handler.py backend/tests/unit/test_question_engine.py`: **34 passed**
6. `pytest -q backend/tests/integration/test_case_api.py backend/tests/integration/test_diagnosis_api.py backend/tests/integration/test_health_api.py`: **28 passed**
7. `pytest -q backend/tests/unit/test_persistence_safety.py`: **17 passed**
8. Full backend suite (`pytest -q backend`): **210 passed, 12 warnings in 12.75s**
9. Task packet validation (`validate_task.py`): **VALID**
10. `git diff --check`: **Clean (0 whitespace errors)**

### Limitations and follow-up

- All acceptance criteria are satisfied with complete verification evidence.
- The task is ready for review by ChatGPT.

### Proposed commit message

`test(api): finalize check rollback verification`

