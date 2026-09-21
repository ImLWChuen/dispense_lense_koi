---
task_id: DLK-M3-032
reviewed_commit: f39444dc1f6353be69769ce1e3ddcd853b14c09a
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-032

## Decision

Changes requested. The committed implementation correctly consolidates recognized defect codes such as `D03_INCONSISTENT_SIZE`, preserves null-code categories, and passes the focused and full backend suites. One bounded correction is required before acceptance because unknown non-null codes do not yet have the deterministic label promised by the task.

## Acceptance evidence

- Reviewed exact local commit `f39444dc1f6353be69769ce1e3ddcd853b14c09a` on `backend-database`.
- The commit changes only `backend/app/api/analytics.py` and `backend/tests/integration/test_analytics_api.py`.
- Recognized codes are consolidated by code and use the canonical name from `get_defect_by_code`.
- Null-code records remain grouped by recorded name and retain `code: null`.
- Focused analytics suite: `16 passed`.
- Full backend suite: `507 passed`, with 42 existing deprecation warnings.
- Committed whitespace check passed.

## Findings

### R1 — Unknown non-null defect names remain query-order dependent (medium)

- `backend/app/api/analytics.py:597` selects the first encountered stored name for an unknown code through `d_name or d_code.replace(...)`.
- `raw_defect_counts` has no ordering, so database execution order decides whether `D99_UNKNOWN_ANOMALY` is labelled `Custom Anomaly`, `Custom Anomaly Variant`, or another stored variant.
- `backend/tests/integration/test_analytics_api.py:976` permits three different labels, so the test does not prove the stated deterministic behavior.
- Use one deterministic policy for unknown non-null codes. The simplest safe policy is always deriving the label from the code, for example `D99 Unknown Anomaly`, regardless of stored-name row order. Tighten the regression test to require that single result and retain the combined count.

## Follow-up

Gemini should make the bounded R1 correction, rerun the focused analytics tests and full backend suite, and create one new local correction commit. Do not amend `f39444d`, push, merge, rebase, or create a pull request. The detailed correction prompt is supplied in chat for copy-paste use.
