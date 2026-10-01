---
task_id: DLK-M3-040
reviewed_commit: 9a8e2a53270e61d7060a6342d0ee6f25a7abdf1a
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-040

## Decision

Changes requested. The additive report field and revision-filtered persisted observation projection are sound, but PDF bounding and unknown/malformed evidence handling do not meet the task contract.

## Acceptance evidence

- Report assembly uses get_case_observations with max_revision=effective_revision, filters IMAGE sources, preserves metadata, and introduces no writes or diagnostic recalculation. The schema has a backward-compatible empty-list default.
- Gemini reports 37 focused tests and 598 full backend tests passed, with task validation VALID. Reviewer inspected the diff and tests without rerunning suites under the planner/reviewer role split. Committed whitespace check passes.
- Current stress tests bound region_evidence but supply only one short affected ID per observation; malformed tests check wrong outer container types but not invalid scalar values inside measurement dictionaries.
- Visual rendering was not performed, as explicitly reported by Gemini. That permitted limitation is not itself a blocking finding.

## Findings

### R1 — P2: Unbounded metadata still enters unsplittable PDF cells

In pdf_generator.py around lines 913–922, every affected ID is joined into one summary-table cell, independently of the 50-region bound. Applied limits serialize every key/value through _escape without truncation, scalar validation, or an allowlist. _fmt_num around line 113 also stringifies arbitrary non-numeric dictionaries/lists/strings without a bound. A persisted observation with many long IDs or a long value under coverage_ratio/applied_limits can therefore create a cell taller than a page and cause ReportLab LayoutError instead of a PDF. HTML escaping does not bound layout or make arbitrary values valid measurements.

Bound affected-ID presentation with explicit omitted counts, allowlist known limit names and validate their finite scalar values, and treat invalid measurement scalars as unavailable rather than rendering their representations. Apply the 200-character limit consistently to rendered user strings. Keep rows split-safe even at the maximum allowed display sizes; do not put the whole affected-ID list in one unbounded row. Add cases combining 50 long canonical ROI IDs, more than 50 affected IDs, long/nested limit values, and invalid numeric fields. Assert successful PDF generation and truthful omission/unavailable notices while JSON remains unchanged.

### R2 — P2: Renderer invents scope and accepts noncanonical status overrides

At lines 903–911, missing or unrecognized region_evidence_scope becomes individual_regions with the positive description Individual region defect findings. At lines 1016–1024, noncontract entry-level site_id and inspection_status override canonical roi_id and current_measurements.inspection_status. The new fixtures explicitly use DEFECTIVE and ACCEPTABLE, whereas the accepted inspection statuses are DETECTED, MISSING, and UNASSESSED and do not constitute process pass/fail. Nested invalid scalar values likewise appear as measurements through _fmt_num. This can misrepresent old/malformed metadata as valid inspection evidence, contrary to the unknown-state requirement.

Render missing/unknown scope as not recorded/unknown, read canonical roi_id and nested inspection_status, and validate status/scalar types for presentation. Do not infer inspection acceptance. Update positive fixtures to the actual DLK-M3-039 contract and add negative tests for missing scope, conflicting entry-level aliases, invalid status, and malformed scalar fields. Include at least one actual _sync_analyze_image-to-case-to-JSON/PDF scenario to verify the producer contract. The reference display also omits has_bubbles from the promised 15-field allowlist; include it without inventing values.

## Follow-up

Gemini should correct R1/R2 within the existing DLK-M3-040 scope, rerun focused/full checks on final corrected code, update the implementation report and queue, and commit locally. No next feature task, push, PR, or merge is authorized. Preserve unrelated files.
