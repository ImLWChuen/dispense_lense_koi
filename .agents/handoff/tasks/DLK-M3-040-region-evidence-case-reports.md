---
task_id: DLK-M3-040
title: Include persisted region evidence in case reports
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-039]
feature_branch: backend-database
base_branch: main
---

# DLK-M3-040: Region evidence in case reports

## Objective

Expose saved image observations and their per-region evidence in the existing JSON case report and downloadable PDF. Engineers should be able to see which sites supported an image finding, their recorded measurements, and the supplied limits without rerunning inspection. This is a bounded Phase 4 report integration increment; it does not complete the visual inspection workbench.

## Current evidence

- DLK-M3-039 is accepted at `641328c0210cd31b56a50717792958fd39886bd3`. Its accepted review and queue changes are pending planner artifacts to include unchanged in the implementation commit.
- Image observations now carry `affected_roi_ids`, `region_evidence_scope`, `applied_limits`, and `region_evidence` with detached current/reference scalar measurements. Durable persistence is already covered by `test_image_driven_case_workflow.py`.
- `backend/app/services/reporting/report_generator.py::build_case_report` pins a diagnosis revision and audit histories but does not project saved observations into `CaseReportResponse`.
- `CaseRepository.get_case_observations(case_id, max_revision=...)` already filters by first_seen_revision and orders by database ID. Use this existing read path; no migration or repository change is needed.
- `CaseObservationResponse` already represents IDs, provenance, timestamps, first_seen_revision, and metadata. `pdf_generator.py` renders exclusively from `CaseReportResponse` and currently shows evaluated cause evidence but no region snapshots.
- Existing report integration tests cover read-only behavior, no diagnostic recalculation, and concurrent writes with a pinned report basis. PDF tests use the installed pypdf dependency.

## Requirements

- Add the backward-compatible field `image_observations: list[CaseObservationResponse]` with an empty-list default to `CaseReportResponse`. Do not add an alias. Populate it only from persisted observations whose source is IMAGE and whose first_seen_revision is at most the report's effective revision.
- Reuse the existing repository query with max_revision set explicitly. Preserve its deterministic ordering, IDs, timestamps, provenance, and full existing metadata. Map values consistently with existing durable case responses. Do not query unbounded latest observations and leak newer evidence into a pinned report.
- Report assembly remains read-only: no writes, diagnosis recalculation, image analysis, metadata repair/backfill, or new storage. JSON exposes persisted contents as recorded, including legacy observations with empty metadata.
- Add a clearly titled Image inspection evidence section to the existing standard case PDF. Render only the supplied report model; no repository access from the PDF renderer.
- For each displayed observation, show its observation type/value, source, statement type, first-seen revision, affected IDs where recorded, and region-evidence scope. Show supplied limits as configuration, explicitly not a claim that every limit failed.
- For well-formed region entries, show the site ID and current measurements, plus separately labeled reference measurements when available. Use the DLK-M3-039 fixed 15-field scalar allowlist, meaningful labels, and units where known. Keep pixel quantities distinct from millimetres; null physical diameter means not recorded. Do not dump arbitrary metadata, raw images, outlines, masks, or bubble details into the PDF.
- Mark comparison_group findings as group comparisons; participants are not individually confirmed failures. Image findings are observations/inferences, not confirmed root causes, and absence of image findings does not mean inspection passed or coverage was complete.
- Handle historical or malformed metadata gracefully. Missing snapshots must say detailed region evidence was not recorded. Do not reconstruct missing per-site measurements from the legacy first-site scalar fields. Unexpected lists/dictionaries/scalars or invalid snapshot entries must not crash PDF generation or be silently represented as valid measured evidence. Distinguish unavailable reference data from measured zero.
- Preserve explicit unknowns and escape all user-controlled strings before ReportLab paragraph rendering. Use wrapping and split-friendly layouts rather than one enormous table row per observation; long IDs, many regions, and multiple pages must remain printable.
- Bound the PDF presentation to the first 20 image observations and first 50 region entries per displayed observation, retaining order and clearly stating omitted counts. Bound individual strings at 200 characters with a visible truncation marker and notice. JSON remains lossless. These display limits must never imply omitted sites passed or inspection was complete.
- Leave all existing report sections, lifecycle distinctions, score labels, and endpoints intact. No new defect interpretation, confidence calculation, frontend page, or 8D report changes.

## Interfaces and data contracts

Authorized additive public response field: `CaseReportResponse.image_observations`, defaulting to `[]`, using the existing `CaseObservationResponse`. Existing JSON/PDF routes and query parameters remain unchanged. Old report payloads without the field must still validate; PDFs built from them show a neutral no-recorded-image-evidence notice.

The JSON field is an ordered persisted-evidence projection, scoped by first_seen_revision to the same effective revision as the rest of the report. It is not a newly calculated inspection result. Current/reference snapshots are independent namespaces and supplied limits describe the recorded configuration. Do not expose current/reference inspection coverage unless it was actually persisted; the new metadata does not establish full coverage or contain the original images.

## Allowed paths

- `backend/app/schemas/case.py`
- `backend/app/services/reporting/report_generator.py`
- `backend/app/services/reporting/pdf_generator.py`
- `backend/tests/unit/test_report_generator.py`
- `backend/tests/integration/test_case_report_api.py`
- `backend/tests/integration/test_case_report_pdf_api.py`
- `docs/api/api-spec.md`
- `docs/architecture/region-inspection-improvement-plan.md` (brief Phase 4 progress note)
- `.agents/handoff/tasks/DLK-M3-040-region-evidence-case-reports.md`
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/reviews/DLK-M3-039-review.md` (include accepted planner review unchanged)

## Prohibited scope

Database/repository changes, migrations, image retention, classifier/segmentation changes, scoring, frontend, 8D reporting, dependencies, route redesign, production data modification, remote Git operations, or changes to main. Preserve unrelated `.agents.zip` and `.agents/handoff/reviews/PROJECT-PROGRESS-2026-09-19.md`.

## Implementation guidance

1. Read applicable instructions, PROJECT.md, QUEUE.md, accepted prerequisite review, report schemas/assembler/renderer, repository read method, and existing report tests. Confirm backend-database and pending planner artifacts.
2. Add report projection tests for two distinct image sites, non-image exclusion, legacy metadata, and a later-revision observation excluded from an earlier pinned report. Verify the missing feature before implementing the additive field/mapping.
3. Populate the field through the existing revision-filtered query. Keep report basis resolution unchanged. Extend existing mocks deliberately rather than relying on empty MagicMock iteration to mask the new read path.
4. Add the bounded PDF section with robust metadata validation, allowlisted scalar presentation, escaped text, and split-friendly layout. Keep reference values and group semantics explicit.
5. Test actual persisted metadata through JSON and PDF, including distinct site values, later-revision isolation, legacy/empty/malformed snapshots, markup-like IDs, null reference/physical calibration, and many regions/long strings. Check omitted-count notices. Retain read-only/no-recalculation/concurrent-write regression coverage.
6. Render a representative multi-page synthetic PDF using existing tools and visually inspect it if available. Record the inspection method and result; do not claim a visual check from text extraction alone. Do not install dependencies or commit generated PDFs. Automated structural/text/layout checks remain required even if a viewer is unavailable.
7. Update API documentation and roadmap, run required checks against final code, complete this report, set queue to implemented, and commit locally.

## Acceptance criteria

- [x] JSON reports expose only persisted IMAGE observations belonging to their effective revision, in deterministic order, with IDs and metadata preserved.
- [x] Later observations cannot leak into an earlier report during concurrent writes; existing read-only and no-recalculation properties remain proven.
- [x] PDF includes correct distinct site measurements, supplied limits, current/reference labels, and group-versus-individual semantics from the same report model.
- [x] Legacy/empty/malformed metadata renders neutral explanatory notices without fabricated values, crashes, or raw arbitrary metadata dumps.
- [x] Long strings and many sites produce a valid readable multi-page document with explicit truncation/omission notices; user text is escaped.
- [x] Default compatibility supports old report objects without image_observations; existing endpoints and sections continue to work.
- [x] Focused/full checks pass on final code, report evidence is truthful, and only scoped files are committed.

## Verification

From repository root in PowerShell, using the existing safe disposable TEST_DATABASE_URL setup. Preserve development data; do not bypass destination safeguards or print credentials.

1. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_report_generator.py backend/tests/integration/test_case_report_api.py backend/tests/integration/test_case_report_pdf_api.py -q --basetemp=backend/.task040-focused -p no:cacheprovider`
2. `& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task040-full -p no:cacheprovider`
3. `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-040-region-evidence-case-reports.md`
4. `git diff --check` and inspect staged changes for generated files/secrets/unrelated edits.

Record actual outcomes. If required automated checks cannot run, mark blocked and describe the blocker. A visual-rendering tool being unavailable may be recorded as a limited verification gap without blocking this task if structural/text, stress, and layout checks pass; do not describe the PDF as visually verified in that case.

## Planner decision boundaries

The additive report field, read-only projection, and bounded standard PDF presentation are authorized. Return to the planner before changing storage, report basis semantics, diagnostic meaning, score handling, dependencies, image retention, other owners' frontend, or scope. If persisted evidence cannot be scoped using the existing revision filter, report that issue rather than broadening repository changes.

## Git instructions

Create one atomic local commit on backend-database after checks pass. Include this completed task packet, queue, and pending accepted DLK-M3-039 review unchanged. Do not push, merge, rebase, create a PR, or modify main.

Proposed commit message: `feat(reports): include persisted region inspection evidence`

## Implementation report

### Summary

Exposed persisted `IMAGE` observations and their per-region inspection evidence in `CaseReportResponse.image_observations` and added Section 8 ("8. Image Inspection Evidence") to standard downloadable case report PDFs (`render_case_report_pdf`).

Report assembly queries `CaseRepository.get_case_observations(case_id, max_revision=effective_revision)` to ensure revision isolation: observations created in subsequent revisions cannot leak into an earlier pinned report. Non-image observations (`USER`, `SYSTEM`) and observations beyond `effective_revision` are strictly excluded while preserving deterministic database ID ordering, timestamps, and full existing metadata.

PDF Section 8 renders exclusively from the supplied `CaseReportResponse` read model (zero database or repository access in the PDF renderer). The layout displays:
- Required notice that image findings represent automated visual observations and inferences, not confirmed root causes, and absence does not imply inspection passed.
- Display bounds: first 20 image observations, and first 50 regions per observation, with visible omission notices stating unlisted sites are not implied to have passed.
- String truncation at 200 characters with visible `[truncated (exceeds 200 chars)]` marker; all user-controlled text is HTML-escaped.
- Distinct scope labeling: `individual_regions` versus `comparison_group` (with group participant note).
- Applied limits labeled as a configuration snapshot, explicitly not an assertion of failure for all limits.
- Split-friendly 4-column region evidence table showing Site ID, status, current 15-field scalar snapshot (`deposit_area_px`, `equivalent_diameter_px`, `calibrated_diameter_mm`, `circularity`, `solidity`, `convexity`, `aspect_ratio`, `hole_void_ratio`, `bubble_count`, `has_bubbles`, `segmentation_quality`, `coverage_ratio`, `overflow_ratio`, `target_area_px`, `inspection_status`), and reference measurements when recorded.
- Robust handling of legacy/empty/malformed metadata displaying neutral explanatory notices without crashing or fabricating measurements.

### Files changed

- `backend/app/schemas/case.py`: Added additive field `image_observations: list[CaseObservationResponse] = Field(default_factory=list)` to `CaseReportResponse`.
- `backend/app/services/reporting/report_generator.py`: Added `_map_observation` and `_get_obs_metadata` mapping functions; populated `image_observations` in `build_case_report` using `repository.get_case_observations(case_id, max_revision=effective_revision)`.
- `backend/app/services/reporting/pdf_generator.py`: Implemented Section 8 ("8. Image Inspection Evidence") with bounding, allowlisted scalar formatting, string truncation, HTML escaping, and neutral notices for empty/legacy/malformed metadata.
- `backend/tests/unit/test_report_generator.py`: Added unit tests for observation mapping, image observation projection, non-image exclusion, legacy metadata preservation, and max_revision isolation.
- `backend/tests/integration/test_case_report_api.py`: Added integration tests verifying `image_observations` in JSON reports, revision isolation against later observations, and backward compatibility.
- `backend/tests/integration/test_case_report_pdf_api.py`: Added integration tests verifying Section 8 in downloadable PDF, distinct site measurements, group comparison notes, applied limits notices, neutral notice for empty evidence, malformed metadata resilience, and 20-obs / 50-region / 200-char truncation notices.
- `docs/api/api-spec.md`: Documented `image_observations` in `CaseReportResponse` specification, updated example response, and updated Section 10 PDF rendered document structure.
- `docs/architecture/region-inspection-improvement-plan.md`: Added Phase 4 progress note for DLK-M3-040.
- `.agents/handoff/QUEUE.md`: Updated DLK-M3-040 status to `**implemented**`.
- `.agents/handoff/tasks/DLK-M3-040-region-evidence-case-reports.md`: Updated status, checked acceptance criteria, recorded verification evidence.
- `.agents/handoff/reviews/DLK-M3-039-review.md`: Included accepted prerequisite review unchanged.

### Decisions made

- Reused existing `repository.get_case_observations(case_id, max_revision=effective_revision)` with zero repository or database schema modifications; report assembly remains strictly read-only and no recalculation is performed.
- Retained strict backward compatibility for `CaseReportResponse`: defaults `image_observations` to `[]`, contains no alias, and satisfies `extra="forbid"`.
- Formatted PDF Section 8 using split-friendly 4-column tables (`[75, 55, 210, 200]` pt totaling 540 pt printable width on letter page with 36 pt margins) allowing clean multi-page document pagination.
- Enforced bounding at 20 observations, 50 regions, and 200 characters per string with visible notices to ensure stable rendering regardless of input data scale.

### Verification results

- Focused test suite:
  `$env:TEST_DATABASE_URL="postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test"; & .\backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_report_generator.py backend/tests/integration/test_case_report_api.py backend/tests/integration/test_case_report_pdf_api.py -q --basetemp=backend/.task040-focused -p no:cacheprovider`
  Result: 37 passed, 13 warnings in 13.55s.
- Full backend test suite:
  `$env:TEST_DATABASE_URL="postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test"; & .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=backend/.task040-full -p no:cacheprovider`
  Result: 598 passed, 42 warnings in 60.12s.
- Task validation:
  `& .\backend\.venv\Scripts\python.exe .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-040-region-evidence-case-reports.md`
  Result: VALID.
- Whitespace check:
  `git diff --check`
  Result: Clean (exit code 0).

### Limitations and follow-up

- Visual PDF rendering libraries (`fitz`, `pdf2image`, `pypdfium2`) are not installed in the backend environment. Verified through automated PDF parsing (`pypdf.PdfReader`), structural inspection, string escaping, multi-page layout up to 16 pages, and exact text extraction without installing unapproved dependencies.
- This completes Phase 4 report integration. Visual region overlays on the frontend workbench, partial score-bearing analysis, and real-image evaluations remain for subsequent tasks.

### Proposed commit message

`feat(reports): include persisted region inspection evidence`

Record the resulting commit hash in the completion message.
