---
task_id: DLK-M3-040
reviewed_commit: e7ce38392e2e3dfb619f8b0441401a2aa3996ae3
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-040

## Decision

Changes still requested after correction e7ce383. The main R1/R2 issues are addressed: affected IDs and limits are chunked, nonnumeric measurements are marked unavailable, missing scope is unknown, canonical ROI/status fields are used, reference has_bubbles is displayed, and a real producer-to-report test was added. Remaining malformed-value crash paths are recorded as R3 below.

## Correction review of e7ce383

- Gemini reports 38 focused tests and 599 full backend tests passed on the correction, task validation VALID, and whitespace checks clean. Reviewer inspected code/tests and independently checked committed whitespace; did not rerun tests.
- New stress coverage includes long canonical ROI IDs, 60 affected IDs, nested invalid measurement/limit values, and JSON preservation. Producer-to-case-to-report coverage now uses actual synthetic image analysis.
- R1/R2 historical findings below are substantially resolved; final acceptance is blocked by R3.

### R3 — P2: Some malformed JSON values still crash PDF rendering

In pdf_generator.py lines 1159 and 1196, membership testing raw_status/ref_raw_status against a frozenset happens before checking the value is a string. Persisted JSON such as inspection_status: [] or inspection_status: {} raises TypeError (unhashable type), rather than rendering UNKNOWN. Both current and reference branches are affected.

Numeric checks at lines 118, 991, 1167, and 1204 call math.isfinite on arbitrary JSON integers. An integer such as 10**400 cannot convert to a float and raises OverflowError. Such metadata is not rejected by the observation metadata dictionary contract. This bypasses the intended unavailable fallback and can make the PDF endpoint return 500.

Guard status types before set membership. Centralize exception-safe finite-number validation for measurement, limit, and physical-diameter paths; preserve unavailable/unknown semantics and bound numeric display if needed. Add API-level regressions for current/reference list/dict statuses and oversized integer values in both measurement and applied-limit fields. Verify PDF success and neutral notices while JSON preserves the original metadata. Rerun focused/full checks on corrected code and record actual results.

## Acceptance evidence

- Report assembly uses get_case_observations with max_revision=effective_revision, filters IMAGE sources, preserves metadata, and introduces no writes or diagnostic recalculation. The schema has a backward-compatible empty-list default.
- Gemini reports 37 focused tests and 598 full backend tests passed, with task validation VALID. Reviewer inspected the diff and tests without rerunning suites under the planner/reviewer role split. Committed whitespace check passes.
- Current stress tests bound region_evidence but supply only one short affected ID per observation; malformed tests check wrong outer container types but not invalid scalar values inside measurement dictionaries.
- Visual rendering was not performed, as explicitly reported by Gemini. That permitted limitation is not itself a blocking finding.

## Historical findings from 9a8e2a5

### R1 — P2: Unbounded metadata still enters unsplittable PDF cells

In pdf_generator.py around lines 913–922, every affected ID is joined into one summary-table cell, independently of the 50-region bound. Applied limits serialize every key/value through _escape without truncation, scalar validation, or an allowlist. _fmt_num around line 113 also stringifies arbitrary non-numeric dictionaries/lists/strings without a bound. A persisted observation with many long IDs or a long value under coverage_ratio/applied_limits can therefore create a cell taller than a page and cause ReportLab LayoutError instead of a PDF. HTML escaping does not bound layout or make arbitrary values valid measurements.

Bound affected-ID presentation with explicit omitted counts, allowlist known limit names and validate their finite scalar values, and treat invalid measurement scalars as unavailable rather than rendering their representations. Apply the 200-character limit consistently to rendered user strings. Keep rows split-safe even at the maximum allowed display sizes; do not put the whole affected-ID list in one unbounded row. Add cases combining 50 long canonical ROI IDs, more than 50 affected IDs, long/nested limit values, and invalid numeric fields. Assert successful PDF generation and truthful omission/unavailable notices while JSON remains unchanged.

### R2 — P2: Renderer invents scope and accepts noncanonical status overrides

At lines 903–911, missing or unrecognized region_evidence_scope becomes individual_regions with the positive description Individual region defect findings. At lines 1016–1024, noncontract entry-level site_id and inspection_status override canonical roi_id and current_measurements.inspection_status. The new fixtures explicitly use DEFECTIVE and ACCEPTABLE, whereas the accepted inspection statuses are DETECTED, MISSING, and UNASSESSED and do not constitute process pass/fail. Nested invalid scalar values likewise appear as measurements through _fmt_num. This can misrepresent old/malformed metadata as valid inspection evidence, contrary to the unknown-state requirement.

Render missing/unknown scope as not recorded/unknown, read canonical roi_id and nested inspection_status, and validate status/scalar types for presentation. Do not infer inspection acceptance. Update positive fixtures to the actual DLK-M3-039 contract and add negative tests for missing scope, conflicting entry-level aliases, invalid status, and malformed scalar fields. Include at least one actual _sync_analyze_image-to-case-to-JSON/PDF scenario to verify the producer contract. The reference display also omits has_bubbles from the promised 15-field allowlist; include it without inventing values.

## Follow-up

Gemini should complete R3 within the existing DLK-M3-040 scope, rerun focused/full checks on final corrected code, update the implementation report and queue, and commit locally. No next feature task, push, PR, or merge is authorized. Preserve unrelated files.
