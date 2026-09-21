---
task_id: DLK-M3-032
reviewed_commit: 01640a7fb3344d49a3dedc478d75ad3bc7f1d475
decision: accepted
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-032

## Decision

Accepted at `01640a7fb3344d49a3dedc478d75ad3bc7f1d475`. The correction resolves R1 by deriving unknown non-null labels solely from their defect code and tightening the regression test to one exact expected label. Recognized-code consolidation and null-code behavior remain intact.

## Final correction review: `01640a7fb3344d49a3dedc478d75ad3bc7f1d475`

### Resolved

- R1 is resolved: unknown non-null codes now use `d_code.replace("_", " ").title()` regardless of stored defect-name variants or database row order.
- The `D99_UNKNOWN_ANOMALY` regression now requires the exact deterministic label `D99 Unknown Anomaly` and still verifies the combined count.
- The correction changes only the intended backend branch, regression assertion, and previously pending handoff records.

### Final verification

- Focused analytics suite: `16 passed`, with 11 dependency deprecation warnings.
- Full backend suite: `507 passed`, with 42 dependency/API deprecation warnings.
- Commit and working-tree whitespace checks passed.

## Acceptance evidence

- Reviewed exact local commit `f39444dc1f6353be69769ce1e3ddcd853b14c09a` on `backend-database`.
- The commit changes only `backend/app/api/analytics.py` and `backend/tests/integration/test_analytics_api.py`.
- Recognized codes are consolidated by code and use the canonical name from `get_defect_by_code`.
- Null-code records remain grouped by recorded name and retain `code: null`.
- Focused analytics suite: `16 passed`.
- Full backend suite: `507 passed`, with 42 existing deprecation warnings.
- Committed whitespace check passed.

## Findings

### Historical R1 — Unknown non-null defect names remained query-order dependent (resolved)

- `backend/app/api/analytics.py:597` selects the first encountered stored name for an unknown code through `d_name or d_code.replace(...)`.
- `raw_defect_counts` has no ordering, so database execution order decides whether `D99_UNKNOWN_ANOMALY` is labelled `Custom Anomaly`, `Custom Anomaly Variant`, or another stored variant.
- `backend/tests/integration/test_analytics_api.py:976` permits three different labels, so the test does not prove the stated deterministic behavior.
- Use one deterministic policy for unknown non-null codes. The simplest safe policy is always deriving the label from the code, for example `D99 Unknown Anomaly`, regardless of stored-name row order. Tighten the regression test to require that single result and retain the combined count.

## Follow-up

No further DLK-M3-032 correction is required. Remote Git operations remain unauthorized until the user explicitly requests them.
