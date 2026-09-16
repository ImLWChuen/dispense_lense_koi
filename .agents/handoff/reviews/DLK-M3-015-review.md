---
task_id: DLK-M3-015
reviewed_commit: 9ad094cfa3b56e3042996238ce4acc0752f9f98c
decision: changes_requested
reviewed_by: ChatGPT planner
---

# Review: DLK-M3-015

## Decision

Changes requested for the two bounded verification gaps below. The swallowed-assertion finding is resolved; no production-code defect or production change is requested here.

## Acceptance evidence

- Inspected the committed test/helper changes, task report, and prior correction requirements at the exact commit above. Working tree was clean before review, on backend-database.
- API and repository hooks capture detached pending-row values and set fault_reached immediately before the deliberate RuntimeError. Evidence assertions now execute outside request/repository exception handling; listener removal is protected by finally.
- Target and control comparisons use independent sessions and include stored revision JSON. Both unfinished-state regressions now compare baseline state rather than counts alone.
- Gemini reports a restored temporary incorrect-check-ID perturbation producing the intended assertion failure despite HTTP 500, 23 check API tests, 28 persistence tests, and 209 full backend tests passing. These are implementer-reported results; the reviewer did not rerun the database suite.
- Reviewer task validation returned VALID and the committed diff passed whitespace inspection. No production files changed.

## Findings

### R1 — P2: Exercise preservation of an existing check history

The rollback targets in backend/tests/integration/test_check_result_api.py:550 and backend/tests/integration/test_persistence.py:1981 are advanced only through a question answer. Their check_results baselines remain empty. The packet explicitly requires nonempty prior question/check histories for the rollback target. These tests establish removal of a failed first check but cannot detect corruption of a previously stored check event during a later failed submission.

In each rollback test, persist a valid prior check through existing operations before capturing the baseline. Assert both question_answers and check_results are nonempty, derive the next revision dynamically, then fail a subsequent evidence-producing check and compare the complete prior state. Keep the full control-case comparison and fault marker.

### R2 — P2: Preserve exact stored values in the snapshot helper

backend/tests/case_snapshot_helper.py:45 and similar expressions for method, defect fields, original_text, answer_text, finding_details, and outcome normalize empty strings to None. A stored value changing from an empty string to SQL NULL therefore produces identical snapshots, contradicting the task's exact preservation contract. Return stored scalar values unchanged (with deep copies only where needed); do not use truthiness to normalize optional text. Add a focused helper-level check showing an empty string and None produce different captured snapshots for a supported field. Also capture the complete pending result_snapshot in both rollback hooks as required by the packet; has_snapshot and snapshot_keys currently retain only presence/shape, not the snapshot contents.

## Follow-up

Planner should include these remaining test-only corrections in the next bounded packet. Keep the resolved outside-request assertions intact. No new task was generated in this review. DLK-M3-015 and its prior correction chain remain unaccepted. No commit, push, or merge was performed; review and queue updates remain local.
