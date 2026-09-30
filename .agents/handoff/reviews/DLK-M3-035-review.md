---
task_id: DLK-M3-035
reviewed_commit: 65798812e104c620470ab66d57a06d02dca38407
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-035

## Decision

Changes requested for two inaccurate contract/report statements. The implementation of ordered affected ROI IDs appears to meet the task's behavior requirements; no code correction has been identified in this review. Correct the documentation and report before acceptance so downstream teammates do not rely on false semantics.

## R1 — P2: API spec incorrectly promises disjoint affected-site lists

Location: `docs/api/api-spec.md` in “Affected Region Provenance in Deduplicated Observations.”

It says different defect values produce “disjoint affected lists.” The classifier can emit `deposit_shape=tailing` and `deposit_shape=abnormal` for the same ROI when that ROI violates both rule conditions; their affected lists then overlap. The task requires separate **exact** lists, not disjoint lists. Replace the blanket disjoint claim with the accurate rule: each observation lists the sites that triggered its own type/value, and lists may overlap when one site triggers multiple rules. The undersized/oversized example can remain as an example, not a universal guarantee.

## R2 — P2: Report incorrectly says unmatched reference sites suppress all observations

Location: `.agents/handoff/tasks/DLK-M3-035-affected-region-provenance.md`, “Limitations and follow-up.”

The report says unmatched ROIs in REFERENCE_IMAGE mode “trigger safe zero-observation gating.” The classifier at `backend/app/services/vision/defect_classifier.py` warns and skips an unmatched current ROI while continuing to classify matched ROIs. The newly added reference-mode unit test explicitly expects one observation from matched sites alongside a warning for unmatched `r4`. Correct the report to distinguish unmatched-site skip/warning from the existing whole-image UNASSESSED gate. Do not change reference-mode behavior in this task.

## Evidence reviewed

- Exact local commit `65798812e104c620470ab66d57a06d02dca38407` on `backend-database`, scoped to task-allowed paths. The accepted DLK-M3-034 review and its narrow wording correction were included.
- `_record_observation` keeps one observation per `(observation_type, value)`, preserves first-site metadata, and appends ordered unique affected ROI IDs. D03 lists detected positive-area participants of the CV calculation.
- Unit tests cover same/different values, multiple rule dimensions, nonviolating-site exclusion, missing-site skip, D03, and reference matching. Synthetic API tests and durable case create/read tests exercise the metadata path; a diagnosis integration test checks no score increase for two matching sites.
- Gemini reports 65 focused tests, 555 backend tests, and task validation passed. The reviewer inspected the code and tests but did not rerun them under the PROJECT.md planner/reviewer role split. The committed whitespace diff check passed.
- The task packet's acceptance checkboxes remain unchecked despite an implemented report; mark only those supported by completed evidence during the documentation correction.

## Follow-up

Correct R1 and R2, align acceptance checkboxes and queue/report state, run task validation and whitespace checks. Because the correction is documentation-only, do not repeat backend suites unless code changes. Commit locally and return for review. No new feature task was generated and no remote Git operation is authorized.
