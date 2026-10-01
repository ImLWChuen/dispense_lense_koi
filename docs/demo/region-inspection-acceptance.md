# Integrated Region Inspection Acceptance & Demonstration Guide

**Milestone:** DLK-M3-042
**Date:** 2026-10-01
**Status:** Validated acceptance guide & scoped readiness matrix
**Target Environments:** Local competition demo (`http://localhost:3001`, `http://127.0.0.1:8000`)

---

## 1. Overview and Purpose

This document provides a concise, repeatable acceptance guide and scoped readiness assessment for the integrated region inspection workflow delivered across increments DLK-M3-033 through DLK-M3-042.

The workflow integrates:
1. **Optical Image Analysis:** Multi-ROI segmentation, deposit outline extraction, and explicit limit evaluation via OpenCV.
2. **Technician Inspection Workbench:** Inline and studio visual workbench with selectable expected sites, outline overlays, and separate current/reference coverage.
3. **Durable Diagnostic Intake:** Lossless persistence of multi-site region evidence snapshots and applied limits into PostgreSQL cases.
4. **Lifecycle & Revision Tracking:** Revision-scoped persistence across check executions (advancing to Revision 2+).
5. **Multi-Format Reporting:** Lossless JSON reports and audit-ready PDF reports with structured Section 8 Image Inspection Evidence.

> [!IMPORTANT]
> **Readiness Scope Boundary:** This document verifies the *delivered manual-ROI workflow slice* using deterministic synthetic fixtures. It does **not** assert industrial manufacturing accuracy on real-world factory images, nor does it imply that deferred features (reusable profiles, automated alignment, or partial score-bearing evidence) are complete.

---

## 2. Environment Identity & Pre-Demo Setup

| Component | Target Identity | Required Port | Verification Method |
| :--- | :--- | :--- | :--- |
| **Database** | PostgreSQL 16 (`dispenselens-postgres`) | 5432 | `docker ps`, health status `healthy` |
| **Backend API** | `dispense-lens-api` v0.1.0 (FastAPI / Uvicorn) | 8000 | `curl http://127.0.0.1:8000/api/v1/health` |
| **Frontend UI** | `DispenseIQ` / `DispenseLens` (Next.js Turbopack) | 3001 | `curl -I http://localhost:3001/diagnosis/new` |
| **Browser** | Google Chrome 140+ / Edge (Chromium) | N/A | Local interactive or headless CDP |

### Environment Verification Steps

Execute from repository root in Windows PowerShell:

```powershell
# 1. Verify service identity and ensure port 3000 is NOT used
powershell -ExecutionPolicy Bypass -File .\scripts\demo-preflight.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\verify-demo.ps1

# 2. Check backend health
curl.exe -s http://127.0.0.1:8000/api/v1/health
# Expected: {"status":"ok","service":"dispense-lens-api","version":"0.1.0"}
```

---

## 3. Repeatable Step-by-Step Rehearsal Guide

Follow this sequence to rehearse the integrated region inspection workflow using rendered UI controls and explicit synthetic identifiers.

### Step 1: Generate Deterministic Multi-Site Test Image

Generate a reproducible synthetic test image containing two distinct deposits using the checked-in test fixtures from PowerShell:

```powershell
& .\backend\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend'); from tests.fixtures.synthetic_images import create_multi_roi_image; img = create_multi_roi_image(400, 200, [(100, 100, 10), (300, 100, 15)]); open('acceptance_sample.png', 'wb').write(img)"
```

**Image Specifications:**
- **Dimensions:** 400 × 200 pixels (PNG format, 1.3 KB).
- **Deposit 1 (Left):** Center `(100, 100)`, radius 10 px (theoretical area $\approx 314\text{ px}^2$, expected diameter $\approx 20\text{ px}$).
- **Deposit 2 (Right):** Center `(300, 100)`, radius 15 px (theoretical area $\approx 707\text{ px}^2$, expected diameter $\approx 30\text{ px}$).

### Step 2: Navigate to New Diagnosis (`/diagnosis/new`) & Enter Context

- Open `http://localhost:3001/diagnosis/new` in Google Chrome.
- Confirm the sidebar navigation highlights **New Diagnosis**.
- Note the two-column layout: Problem Description & Defect Taxonomy on the left, Image Upload on the right.
- Use standard synthetic demo prefixes:
  - **Symptom Description** (textarea):
    `[SYNTHETIC DEMO] Acceptance Rehearsal: Two distinct dispensed adhesive deposits undersized under process limits.`
  - **Equipment / Line** (dropdown):
    Select `Dispensing Line A` *(or any available line A–D)*.
  - **Material Type** (text input):
    `[SYNTHETIC DEMO] Synthetic Epoxy Adhesive Lot-A1`
  - **Observed Defect Taxonomy** (clickable card):
    Click **Too Little Material** (`D01_TOO_LITTLE`).
  - **Manual Observations** (optional dropdowns):
    - Deposit Size: `Undersized (smaller than target)`
    - Defect Frequency: `Consistent (occurs steadily / every shot)`
    - Defect Location: `All dispensing points (systemic)`

### Step 3: Upload Image & Configure Two ROIs in Workbench

1. **Upload File:** Drop or browse `acceptance_sample.png` into the upload dropzone.
2. **Initial Auto-Analysis State:**
   - On initial file selection, `ImageUpload.tsx` automatically creates a single centered default ROI (`dot-1`) and runs analysis.
   - The upload card expands automatically, showing the image preview and ROI editor.
3. **Configure Two Distinct ROIs (`dot-1` and `dot-2`):**
   - > [!IMPORTANT]
     > **ROI Invalidation Rule:** Adding, deleting, or resetting ROIs immediately invalidates prior analysis results, bumps `configRevision`, and resets upload status to `ready`. Both ROIs must be configured before running analysis and clicking Start Diagnosis.
   - Click the **Reset ROIs** button (counter-clockwise arrow icon in the ROI editor toolbar) to clear the default single ROI.
   - Notice that clearing ROIs automatically switches the interaction toggle to **[ Draw ROI ]**.
   - **Draw Left ROI (`dot-1`):** Click and drag across the left half of the image from approximately normalized `(0.02, 0.02)` to `(0.48, 0.98)`. Confirm `dot-1` appears in the target regions list.
   - **Draw Right ROI (`dot-2`):** Click and drag across the right half of the image from approximately normalized `(0.52, 0.02)` to `(0.98, 0.98)`. Confirm `dot-2` appears and the header displays `2 defined`.
4. **Configure Calibration Limits:**
   - Under **Analysis Mode & Calibration**, ensure Mode is set to **Process Limits** (`PROCESS_LIMITS`).
   - Under **Process Thresholds**, set **Min Coverage Ratio** to `0.10` (matching Scenario A).
5. **Run Analysis:**
   - Click the **Analyze** button (with Play icon) in the image summary bar.
   - Wait for the status badge to display **CALIBRATED** (green badge).
6. **Inspect Rendered Multi-Site Workbench:**
   - **Expected Target Sites:** Observe the tab bar displaying both `dot-1` and `dot-2`.
   - **Inspect `dot-1`:** Click the `dot-1` tab. Confirm status is `DETECTED`. Observed measurements:
     - Coverage Ratio: `~0.89%` (under the 0.10 process threshold $\rightarrow$ undersized).
     - Equivalent Diameter: `~19.96 px` (calibrated physical: `~0.399 mm`).
     - Deposit Area: `~313 px²` (within target area `~35,328 px²`).
     - Outline Overlay: Confirm the 40-vertex SVG polygon aligns with the left deposit boundary.
   - **Inspect `dot-2`:** Click the `dot-2` tab. Confirm status is `DETECTED`. Observed measurements:
     - Coverage Ratio: `~2.00%` (under the 0.10 process threshold $\rightarrow$ undersized).
     - Equivalent Diameter: `~29.96 px` (calibrated physical: `~0.599 mm`).
     - Deposit Area: `~705 px²` (within target area `~35,328 px²`).
     - Outline Overlay: Confirm the 40-vertex SVG polygon aligns with the right deposit boundary.
   - Confirm both sites exhibit distinguishable empirical measurements ($0.89\% \neq 2.00\%$, $20\text{ px} \neq 30\text{ px}$).
   - **Coverage Card:** Confirm "Current Image Inspection Coverage: COMPLETE (Expected: 2, Assessed: 2)" is displayed.

### Step 4: Create Case & Evaluate Deterministic Diagnosis

1. Click the **Start Diagnosis** button at the bottom right.
2. The frontend packages both affected site IDs (`dot-1` and `dot-2`) along with per-region measurement snapshots into the case payload submitted to `POST /api/v1/cases`.
3. **Outcome:** The case is persisted to PostgreSQL at **Revision 1**, and the browser navigates to `/diagnosis/{case_id}` (e.g. `/diagnosis/e1d8db2d-fdce-4edf-974c-97ce671f0792`).
4. **Verify Saved Overview:**
   - Confirm the `REVISION 1` badge is rendered.
   - Note top candidate cause (`Nozzle Restriction`) with deterministic evidence support score (e.g. `62.0 / 100`).
   - Emphasize that scores are deterministic evidence-support metrics, not statistical probabilities or guaranteed fixed rankings across different input combinations.

### Step 5: Inspect Saved Evidence on Saved Case Analysis Page

1. Navigate to the **Analysis Detail** subpage: Click `Analysis Detail` in the workflow stepper or visit `/diagnosis/{case_id}/analysis`.
2. Locate the **Image Analysis Evidence** card:
   - Confirm the card displays `Persisted calibrated visual defect observations`.
   - **Observation Header:** Confirms observation type (`deposit presence`), value badge (`missing`), scope badge (`Individual Regions`), and revision badge (`Rev 1`).
   - **Scope Explanation:** Explicitly explains whether defect criteria triggered per-region (`individual_regions`) or as a comparison group (`comparison_group`).
   - **Summary Cards:** Displays recorded affected site IDs (`dot-1`, `dot-2`) and allowlisted applied limits configuration snapshot (`min_coverage_ratio`, etc.).
   - **Persisted Per-Region Measurements:** Selectable site tabs (`dot-1 DETECTED`, `dot-2 DETECTED`) allow technician review of each site's 15-parameter scalar evidence snapshot:
     - 4-metric primary grid: Coverage ratio (`0.9%` vs `2.0%`), Overflow ratio (`0.0%`), Equivalent diameter (`20.0 px` vs `30.0 px`), Physical diameter (`0.399 mm` vs `0.599 mm`).
     - Geometric morphology: Deposit area (`313 px²` vs `705 px²`), Circularity, Aspect ratio, Solidity, Voids/bubbles, Segmentation quality.
     - Reference measurements: Separately displays reference snapshot (or explicitly notes "Not recorded" when single-image or omitted).
3. **Data Retention Clarification:**
   As stated in the footer note, raw image uploads and full polygon outlines are discarded after analysis and are not retained in durable storage. Durable PostgreSQL case records preserve quantitative scalar measurements, affected target ROI identifiers, and threshold limit snapshots.

### Step 6: Verify Case Records and Download PDF Case Report

1. **Verify Backend Case API (`GET /api/v1/cases/{case_id}`):**
   - Confirm `observations[0].metadata.affected_roi_ids` contains `["dot-1", "dot-2"]`.
   - Confirm `observations[0].metadata.region_evidence` contains 2 distinct snapshots with distinct scalar measurements.
2. **Verify JSON Report API (`GET /api/v1/cases/{case_id}/report`):**
   - Confirm `image_observations[0].metadata.affected_roi_ids` is `["dot-1", "dot-2"]`.
   - Confirm `image_observations[0].metadata.region_evidence` has length 2.
3. **Download PDF Report (`GET /api/v1/cases/{case_id}/report.pdf`):**
   - Content-Type: `application/pdf`.
   - Content-Disposition: `attachment; filename="dispenselens-case-{case_id}-r1.pdf"`.
   - Section **8. Image Inspection Evidence**:
     - Lists observation count and `Affected Sites: dot-1, dot-2`.
     - Displays Applied Limits configuration snapshot (`min_coverage_ratio: 0.1`, etc.).
     - Tabular per-region measurements table renders distinct rows for both `dot-1` and `dot-2` (e.g. `Coverage: 0.0089`, `Diam: 19.96 px` for `dot-1`; `Coverage: 0.02`, `Diam: 29.96 px` for `dot-2`).

---

## 4. Scoped Readiness Matrix

This matrix separates demonstrated capabilities from deferred roadmap features and unmeasured manufacturing accuracy.

| Component / Workflow Slice | Implementation Status | Automated Verification | Demo Readiness | Remaining Gap / Production Limitation |
| :--- | :--- | :--- | :--- | :--- |
| **Multi-ROI OpenCV Segmentation** | Implemented (DLK-M3-033) | 6-case synthetic baseline (DLK-M3-038) | Ready for synthetic demos | Optical tuning based on synthetic fixtures; unvalidated on noisy production cameras. |
| **Bounded Polygon Outlines** | Implemented (DLK-M3-034) | Unit & integration tests | Ready for synthetic demos | Bounded to 3–128 vertices. Omitted for UNASSESSED / MISSING regions. |
| **Affected-Site Provenance** | Implemented (DLK-M3-035) | Deduplication & provenance tests | Ready for synthetic demos | Preserves ordered affected ROI IDs in observation metadata. |
| **Separate Current/Reference Coverage** | Implemented (DLK-M3-036/037) | Integration suites | Ready for synthetic demos | No automatic physical alignment between current and reference substrates. |
| **Per-Region Evidence Snapshots** | Implemented (DLK-M3-039) | Lifecycle round-trip tests | Ready for synthetic demos | 15 scalar metrics captured per site. |
| **Case Report (JSON & PDF) Integration** | Implemented (DLK-M3-040) | pypdf parsing, revision tracking | Ready for synthetic demos | Extracted text and tables verified; visual aesthetic layout unverified by CI. |
| **Frontend Upload Workbench** | Implemented (DLK-M3-041) | CDP browser rehearsal (two-site verified) | Ready for interactive demos | Responsive SVG overlay locked to image content with measured bounds across zoom and aspect ratios. |
| **Saved-Case Multi-Site Display** | **Implemented** (DLK-M3-043) | Unit tests (7/7 passed), browser CDP rehearsal (`04-saved-case-multi-site-evidence.png`) | Ready for interactive and saved-case inspection demos | None for saved-case scalar presentation; raw images/polygons intentionally not retained. |
| **Partial Score-Bearing Evidence** | **Deferred** (Phase 1 gap) | Negative tests (zero obs on partial) | Conservative fail-safe | Partially unassessed calibrated images emit 0 score-bearing observations. |
| **Reusable Profiles & Auto-Alignment** | **Deferred** (Phase 3) | None | Not implemented | Manual ROI configuration required per upload; no layout library. |
| **Industrial Dispensing Accuracy** | **Unmeasured** (Phase 5 gap) | Synthetic benchmark only | **Not ready for production** | No held-out factory dataset, lighting variation tests, or agreed acceptance metrics. |

---

## 5. Documented Limitations and Operational Notes

1. **Saved-Case Multi-Site Presentation Delivered:**
   The saved case page (`/diagnosis/[id]/analysis` via `ImageAnalysis.tsx` and `SavedRegionEvidence.tsx`) now fully presents multi-site evidence with selectable site tabs, 15-parameter scalar measurements, applied limits snapshots, and scope indicators. Legacy cases without `region_evidence` safely fall back to the single-site summary card without crashing or fabricating absent data.
2. **Conservative Quality Gating (No Partial Evidence):**
   If any expected ROI is UNASSESSED in a calibrated image, the system marks the analysis `UNRELIABLE` and emits exactly **zero** score-bearing observations. While per-region measurements are shown in the workbench for technician visibility, the diagnostic engine conservatively refuses to score incomplete evidence.
3. **No Original Image Retention & Transient Outlines:**
   The platform intentionally does **not** persist raw image files or polygon deposit outlines into the database. PostgreSQL case observations persist only `affected_roi_ids`, `applied_limits`, `region_evidence_scope`, and `metadata.region_evidence` (a list of 15 scalar measurements per site). Deposit outlines (`deposit_outline_normalized`) are transient analysis-response data used solely for real-time overlay visualization in the frontend upload workbench; they are not saved in PostgreSQL cases or reports. Saved-image reconstruction from database state alone is completely unavailable.
4. **Visual PDF Layout Inspection Tooling:**
   Automated CI and test scripts parse and verify PDF document structure, headers, affected site IDs, and tabular scalar measurements using `pypdf`. Visual aesthetic layout inspection (margins, line wrapping, pagination, and font rendering) is **unverified** by CI because headless PDF rasterization tools (`pdftoppm`, `mutool`) are not installed on the Windows environment. Full visual layout verification requires manual operator inspection in a desktop PDF viewer.
5. **Synthetic vs. Industrial Data:**
   The offline benchmark (`backend/tests/vision_inspection_baseline.py`) verifies algorithmic repeatability against labeled synthetic fixtures. Field deployment requires team decisions regarding labeled factory image capture, optical lighting controls, and target accuracy thresholds.
