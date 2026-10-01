# Region-based dispensing inspection improvement plan

Date: 2026-09-30
Status: Draft implementation roadmap; inspection scope awaiting user decision. Not a released Gemini task.

## Objective

Inspect expected dispensing sites individually, show the detected material boundaries and evidence, and feed trustworthy observations into the existing troubleshooting assistant. Retain a manual ROI workflow. Reuse existing OpenCV services before considering replacement models.

## Verified starting point

- `backend/app/api/images.py` analyzes each configured ROI and maps segmentation outputs into measurements.
- `backend/app/services/vision/segmentation.py` already returns status, masks, contours, quality, and warnings.
- `RoiMeasurement` currently omits segmentation status and detailed segmentation warnings. The response has no deposit-boundary representation.
- Aggregate measurement logic treats zero-area or absent measurements as missing, which must be distinguished from failed inspection.
- Classification currently rejects the whole measurement set when any supplied region falls below its quality threshold.
- Reference mode uses normalized regions on both images; this is not image registration.
- Repeated observation types are deduplicated, potentially retaining metadata for only the first affected region.

These are inspected implementation facts, not a claim of measured accuracy on real production images.

## Decisions pending

1. Primary input scope: repeated product layouts, varied products, or both with reusable layouts first.
2. Available evaluation images and trustworthy reference labels; confirm whether representative real images can be obtained.
3. Required automation: manually confirmed positions first, or automatic location proposals in the first delivery.
4. Template storage: portable local import/export initially versus shared database storage. Proposed default is portable versioned profiles; shared persistence requires a separately scoped contract.

Proposed initial boundary: top-down dot deposits, manual confirmation of expected sites, explicit reference/process limits, and controlled capture geometry. Lines, arbitrary viewpoints, and fully automatic board understanding require separate validation. These boundaries remain proposals until discussed.

## Required behavior

- Separate segmentation outcome (detected, missing, unassessed), acceptance outcome (within configured limits, outside configured limits, not evaluated), and coverage (complete or partial).
- Missing requires an expected site and adequate evidence of an empty location. Blur, glare, clipping, failed segmentation, or failed alignment must produce unassessed status.
- Without acceptance limits, show measurements without a pass/fail claim. Physical dimensions require valid scale calibration.
- Keep per-region warnings, thresholds, measurements, stable IDs, and affected-region provenance.
- Aggregate only comparable, valid regions. Report numerator and denominator, excluded regions, and insufficient-sample conditions. Never report an overall pass with required sites unassessed.
- Do not multiply diagnostic evidence merely because many regions exhibit the same observation. Preserve existing scoring semantics and aggregate affected ROI IDs.
- Visible surface features do not establish material volume, internal voids, or root causes.
- Editing regions, alignment, calibration, limits, reference image, or current image invalidates prior analysis until rerun.

## Phased delivery

### Phase 0: Fixtures and contract

Select representative images and record supported capture conditions. Prepare synthetic cases for normal, small footprint, large footprint, missing, spread, visible shape anomalies, glare, blur, clipped regions, and mixed reliable/unreliable regions. Define ground-truth boundaries and expected site maps where available.

Specify additive response fields and compatibility behavior for existing clients before implementation. Avoid introducing a new global status that old consumers silently mishandle; inventory consumers first. Document geometry conventions, response-size limits, region limits, and analysis provenance.

Acceptance: reviewed fixture manifest, explicit expected results, agreed supported scope, and a compatible API contract. Synthetic fixtures demonstrate software behavior, not industrial accuracy.

- **Increment DLK-M3-038 Status (Implemented):** Delivered deterministic synthetic fixture manifest (`synthetic_region_inspection_baseline_v1`), offline CLI benchmark runner (`backend/tests/vision_inspection_baseline.py`), and baseline evaluation document (`docs/evaluation/region-inspection-synthetic-baseline.md`). Evaluated 6 scenarios (9 expected sites) covering detected dots, confirmed missing sites with fiducials, uniform unassessed sites, and mixed configurations. Achieved 100% status accuracy, 22.2% abstention, 0.0% false-missing rate, 100% outline availability, and 0.9970 mean IoU against construction-grounded circular masks without altering production code.

### Phase 1: Trustworthy per-region results

Preserve segmentation statuses and warnings through measurement and API layers. Exclude unassessed regions from missing counts and diagnostic observations. Permit valid regions to contribute evidence while explicitly reporting partial coverage. Recompute comparable-region aggregates and preserve affected-site metadata without duplicate scoring.

- **Increment DLK-M3-033 Status (Implemented):** Delivered foundation reliability layer: `RoiInspectionStatus` (`DETECTED`, `MISSING`, `UNASSESSED`), per-region warnings propagation, `unassessed_roi_ids` on aggregates, and conservative whole-image gating in calibrated modes. Unassessed regions are strictly prevented from mislabeling as missing deposits. Overlays, masks/contours, and partial-evidence classification remain for subsequent phases.
- **Increment DLK-M3-035 Status (Implemented):** Delivered affected-region provenance: added `metadata.affected_roi_ids: list[str]` to calibrated `IMAGE` observations. Preserves all violating site IDs in input order without inflating diagnostic evidence scores or creating duplicate observations. D03 inconsistent-size records eligible comparison participants. Lossless persistence verified through durable case create/read.
- **Increment DLK-M3-036 Status (Implemented):** Delivered expected-site inspection coverage summary: added `expected_roi_count: int | null`, `assessed_roi_count: int | null`, and `inspection_coverage_status: InspectionCoverageStatus | null` (`COMPLETE`, `PARTIAL`, `NONE`) to `AggregateMeasurements`. Distinguishes fully inspected, partially inspected, and uninspected current images. Legacy aggregates deserialize safely as unknown (`null`), and calibrated-mode conservative gates remain enforced.
- **Increment DLK-M3-037 Status (Implemented):** Delivered reference-image inspection coverage: added `reference_aggregate_measurements: AggregateMeasurements | None = None` to `ImageAnalysisResponse`. In `REFERENCE_IMAGE` mode with valid uploaded reference, returns the independent reference-image aggregate metrics, counts, and coverage status, while explicitly returning `null` in non-reference modes. Distinguishes reference inspection completeness from comparison suitability and process compliance while preserving conservative gating for unassessed or missing reference deposits.

Acceptance: one blurred region does not erase valid findings elsewhere or become a missing deposit; all-unreliable input produces no diagnostic evidence; existing features-only behavior remains neutral; reference failures are handled per corresponding site.


### Phase 2: Visual inspection workbench

Return bounded contour geometry or a bounded mask representation, with explicit coordinate mapping from analysis windows to the displayed image. Show expected sites, detected material, defects, and unassessed regions. Selecting a region displays its measurements, limits, and short reasons. Distinguish image quality from diagnostic Evidence Support /100.

- **Increment DLK-M3-034 Status (Implemented):** Delivered backend geometry foundation: added typed `deposit_outline_normalized` (`list[NormalizedPoint] | null`) to `RoiMeasurement`. Bounded outer polygon (3–128 finite points) normalized to full image coordinates with window offset translation, deterministic simplification, out-of-bounds rejection, and top-level omission warnings on DETECTED regions. Frontend workbench rendering and reusable profiles remain scheduled for subsequent increments.
- **Increment DLK-M3-041 Status (Implemented):** Delivered frontend visual inspection workbench: added selectable target sites, SVG `<polygon>` deposit outline overlays with selection rings and status-colored bounding boxes in `ImageRoiEditor.tsx`, detailed per-region inspection breakdown in `RegionInspectionPanel.tsx` (coverage, overflow, physical & pixel diameters, morphology metrics, warnings, and emitted observations), distinct current vs reference coverage cards, truthful fallback handling for legacy responses, and letterbox-aware coordinate mapping. Verified via comprehensive automated browser scenarios and live backend integration.

Acceptance: overlays align under image resize and zoom; every configured site has a visible result; corrections invalidate stale outputs; a technician can trace each finding to the image and rule used.

### Phase 3: Reusable profiles and alignment

Scope depends on user decision. For repeated layouts, save versioned expected sites, geometry groups, capture assumptions, and limits. Support manual anchor alignment first if appropriate; evaluate automatic alignment only against representative image pairs. Validate alignment quality and reject unsupported changes in viewpoint, scale, or clipping. Keep expected sites even when no deposit is detected.

For varied products, prioritize per-image ROI editing and optional site proposals requiring confirmation. Do not equate automatically detected blobs with the complete set of expected sites.

Acceptance: profile round-trip preserves IDs and limits; displaced images either align within a fixture-defined tolerance or produce an actionable unassessed result; missing sites remain inspectable. Do not reuse mm-per-pixel blindly after geometric changes.

### Phase 4: Assistant and report integration

Carry inspection provenance into case evidence and reports, using the existing persistence path where possible. Confirm storage boundaries before adding schema or retention changes. Summaries identify affected and unassessed sites and recommend evidence-supported follow-up checks. Keep root-cause confirmation and recovery verification separate.

- **Increment DLK-M3-039 Status (Implemented):** Delivered per-region evidence snapshots and applied limits: enriched calibrated `IMAGE` observations with `region_evidence_scope` (`individual_regions` | `comparison_group`), `applied_limits` (JSON-compatible process or reference bounds), and `region_evidence` (ordered detached scalar snapshots matching `affected_roi_ids`). Preserved legacy first-site metadata and verified lossless persistence through durable case creation, retrieval, and revision 2 in PostgreSQL.
- **Increment DLK-M3-040 Status (Implemented):** Delivered persisted region evidence integration into case reports: projected persisted `IMAGE` observations scoped to the report's effective revision into `CaseReportResponse.image_observations`, and rendered Section 8 ("8. Image Inspection Evidence") in downloadable case report PDFs with bounded 20-observation / 50-region presentation, allowlisted scalar snapshots with units (`px²`, `px`, `mm`), group-versus-individual semantics, applied limits configuration notices, and neutral notices for legacy or malformed metadata.

Acceptance: saved cases and reports preserve the assessed scope, limits, and uncertainties; repeated region findings do not inflate ranking; no image observation is presented as a confirmed cause.

### Phase 5: Evaluation and rehearsal

Measure boundary agreement, per-defect precision/recall where labels exist, missing-site errors, abstention rate, latency, and technician correction effort. Keep images from the same physical board/capture series together when separating development and evaluation data. Set numerical targets after the baseline and before tuning against held-out data; do not invent accuracy claims.

Acceptance: repeatable end-to-end demonstration including a normal image, mixed defects, and an unassessed region; recorded measured results and limitations; affected backend tests and frontend lint/build pass.

- **Increment DLK-M3-038 Status (Implemented):** Established offline synthetic baseline runner and evaluation report (`docs/evaluation/region-inspection-synthetic-baseline.md`) measuring status confusion, abstention, outline availability, and polygon-mask IoU before tuning segmentation on production data.

## Implementation ownership and sequence

Member 3: image result contracts, CV services, API integration, provenance and persistence support. Member 1: region editor, overlays, result presentation. Member 2: evidence projection and diagnostic interpretation review. Gemini executes one bounded task at a time; ChatGPT reviews commits and records decisions. Resolve team ownership for frontend changes before issuing those packets.

First proposed task after scope confirmation: Phase 0 plus the smallest Phase 1 reliability correction, with regression tests. Do not combine templates, automatic alignment, and UI redesign into that first task.

## Verification and Git boundaries

Use a separate disposable test database under existing safeguards; preserve demo records. Discover current focused image/vision suites before issuing exact task commands. Required frontend checks when affected are `npm run lint` and `npm run build` from `frontend/`; backend tests use the established virtual environment. Record actual results, not assumed passes.

Work on `backend-database`, preserve unrelated changes, commit only scoped files locally. Push, PR creation, and merge require explicit user instruction. This roadmap does not release an active task or authorize Gemini to implement all phases together.
