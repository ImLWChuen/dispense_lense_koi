---
task_id: DLK-M3-043
reviewed_commit: fa81f024fe394b233a47cd3d6cfe2406a4f07d41
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-043

## Decision and verification

Follow-up at fa81f024fe394b233a47cd3d6cfe2406a4f07d41: R1–R3 code corrections are resolved on inspection. The component now moves focus with selection, namespaces DOM IDs using useId, clamps collapsed selection, shares complete current/reference scalar rendering and restores legacy fields. Projection distinguishes malformed/empty data and strict absent-scope canonical fallback, retaining full IDs for matching. Gemini reports 8+6+7 focused checks, lint/build and browser boundary checks passing. Committed whitespace check now passes. Reviewer did not rerun execution.

### R4 — P2: Label mocked browser evidence and retain an unmocked reload check

The replacement implementation report calls its suite real-browser verification on live services but does not disclose response substitution. The referenced scratch/verify-saved-case-browser-suite.mjs enables Fetch interception for *api/v1/cases/* and fulfills those requests with a synthetic testCase (around lines 306–320). This is useful real-browser, mocked-API coverage of accessibility/reference/malformed cases, not a live saved-case integration check. The current report also replaces the original real-case evidence rather than retaining its provenance, and does not record the required reload/console check against the final implementation.

Correct the report to explicitly distinguish mocked API browser checks from live backend checks. Retain previous live evidence as historical evidence with its original commit. On the corrected frontend perform a short unmocked load and reload of the existing two-site synthetic case, inspect both sites and limits, and record console errors/warnings, tested source commit, service identity and exact artifact paths. No data mutation, new fixtures in the database or full backend suite is needed. If this final unmocked check was already performed, provide its actual evidence rather than rerunning unnecessarily. No further production-code change is requested for R4. Run task validation and whitespace check after documentation updates; rerun code checks only if code changes.

## Historical initial review (R1–R3 resolved in fa81f02)

Changes requested. The normal two-site path is implemented, within the allowed production paths. Gemini reports projection suites passing (7 new, 6 region-view, 7 upload-state), lint/build success and live browser checks. Reviewer inspected code and reported evidence, without rerunning implementation tests/browser. The committed whitespace check reports a new blank line at EOF in the task packet; remove it during correction. No push or merge performed.

## R1 — P2: Correct tab focus, identity and collapse behavior

In SavedRegionEvidence.tsx, handleKeyDown updates selection but never moves focus. Repeated ArrowRight presses remain relative to the originally focused index, so keyboard navigation stalls rather than traversing the sites. The implementation report's claim that focus moved is not supported by this code. Every tab also has tabIndex=0. DOM IDs use only roi_id, so the same normal site present in two observations produces duplicate tab/panel IDs and incorrect aria-controls/label associations; unique React keys do not fix DOM identity. Collapsing after selecting site 13+ leaves its hidden tab selected and its panel visible.

Use an instance-unique namespace plus snapshot identity for DOM IDs, a roving tab stop and actual focus movement. On collapse or input changes keep selected panel, visible selected tab and focus coherent. Verify three consecutive arrow presses, Home/End, repeated site IDs across observations and within malformed input, and expand/select-after-12/collapse in browser. Record actual document.activeElement, not only selected state.

## R2 — P2: Preserve recorded measurements in current, reference and legacy views

SavedRegionEvidence.tsx parses but does not display current convexity/has_bubbles and renders only four reference fields, hiding stored reference overflow, calibrated diameter, morphology, void/bubble and quality data needed to understand reference findings. The legacy replacement drops previously visible overflow, current/reference coverage, comparison ratio, segmentation quality and size CV; some are still parsed but never rendered. A saved reference observation can therefore lose its comparison explanation after this change.

Expose all supported recorded scalar fields for current and reference separately (a shared measurement renderer is reasonable), preserving finite-value/unknown and unit handling. Restore useful legacy fields without attributing them to every site. Test a reference shape/void case and a legacy reference comparison with distinct values, then verify rendered output, not projection alone. Correct target_area_px limit units to px². Numeric limit fields containing booleans must show unavailable rather than True/False as if valid supplied thresholds.

## R3 — P2: Distinguish malformed snapshots from genuinely legacy evidence

In saved-region-evidence.ts, isLegacyOnly is based on snapshots.length rather than whether region_evidence exists. A present object/string or empty array with legacy fields is shown as an observation saved before multi-site snapshots, silently masking malformed/incomplete evidence. Empty measurement objects also count as usable snapshots, suppressing the missing-snapshot notice. Scope fallback additionally accepts noncanonical deposit_size_cv/inconsistent and overrides explicit unrecognized scope with a group claim.

Track absent, malformed and empty region evidence separately. Only absent snapshots may use a neutral legacy-format explanation; do not infer record age. Preserve usable entries while visibly identifying missing/invalid data. Treat objects with no usable scalar/status content as unavailable. Keep explicit unknown scope unknown and restrict any absent-scope fallback to deposit_size/inconsistent. Add regressions for object/string/empty region_evidence with legacy fields, empty scalar objects, explicit unknown scope and noncanonical D03. Do not invent recorded IDs or associate different long IDs after truncating them; retain full IDs for matching and use display-only truncation/wrapping.

## Correction instructions

Continue DLK-M3-043 within its existing scope. Add focused regressions and affected browser checks, rerun required frontend scripts/lint/build, update the implementation report with actual evidence, remove task EOF whitespace, and commit locally including this review. Do not change backend, storage or scoring. No new task packet, push, PR or merge.
