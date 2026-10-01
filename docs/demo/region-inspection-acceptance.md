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

### Step 1: Navigate to New Diagnosis (`/diagnosis/new`)
- Open `http://localhost:3001/diagnosis/new` in Google Chrome.
- Confirm the sidebar navigation highlights **New Diagnosis**.
- Note the two-column layout: Problem Description & Defect Taxonomy on the left, Image Upload on the right.

### Step 2: Enter Process Context & Defect Type
Use the standard synthetic demo prefixes:
- **Symptom Description** (textarea):
  `[SYNTHETIC DEMO] Acceptance Rehearsal: Dispensed adhesive deposits are visibly smaller than target after continuous operation.`
- **Equipment / Line** (dropdown):
  Select `Dispensing Line A` *(or any available line A–D)*.
- **Material Type** (text input):
  `[SYNTHETIC DEMO] Synthetic Epoxy Adhesive Lot-A1`
- **Observed Defect Taxonomy** (clickable card):
  Click **Too Little Material** (`D01_TOO_LITTLE`).
- **Manual Observations** (optional dropdowns):
  - Deposit Size: `Undersized (smaller than target)`
  - Frequency Pattern: `Consistent (occurs steadily / every shot)`
  - Defect Location: `All dispensing points (systemic)`

### Step 3: Upload Image & Exercise Inspection Workbench
- **Upload Image:** Drop or browse a multi-deposit test image (e.g. 400x200 PNG with deposits at 100,100 and 300,100).
- **Configure Analysis Mode & Calibration:**
  - Select mode: `Process Limits`.
  - Ensure process thresholds are configured: e.g. Min Coverage Ratio `0.15`, Max Coverage Ratio `0.45`.
  - Click `Analyze` *(analysis runs automatically on initial drop)*.
- **Inspect Rendered Workbench:**
  - **Status Badge:** Verify status is `CALIBRATED` (green badge).
  - **Inspection Mode Toggle:** Test switching between `[ Inspect ]` and `[ Draw ROI ]`. Confirm that clicks in Inspect mode select regions without drawing new rectangles, while Draw mode allows adding ROIs.
  - **Expected Target Sites:** Observe the tab bar displaying expected sites (e.g. `dot-1`). Click each tab to inspect detailed geometric measurements (Coverage Ratio, Diameter, Segmentation Quality).
  - **Deposit Outlines:** Confirm the SVG polygon overlay aligns with the detected deposit boundary with zero letterbox drift.
  - **Coverage Card:** Confirm "Current Image Inspection Coverage: COMPLETE" is displayed.

### Step 4: Create Case & Evaluate Deterministic Diagnosis
- Click the **Start Diagnosis** button at the bottom right.
- **Outcome:** The case is persisted to PostgreSQL at **Revision 1**, and the browser navigates to `/diagnosis/{case_id}` (e.g. `/diagnosis/ee5d0200-270c-4fbe-b1e8-5b5182af089a`).
- **Verify Overview:**
  - Point out the `REVISION 1` badge.
  - Point out the top-ranked cause (`Nozzle Restriction`) with deterministic score (e.g. `62.0 / 100`).
  - Emphasize that scores are deterministic evidence-support metrics, not statistical probabilities.

### Step 5: Inspect Saved Evidence & Note Known Presentation Limitations
- Navigate to the **Analysis Detail** subpage: Click `Analysis Detail` in the workflow stepper or visit `/diagnosis/{case_id}/analysis`.
- Locate the **Image Analysis Evidence** card:
  - Confirm the card displays `Persisted calibrated visual defect observations`.
  - Verify stored measurements: `Status: CALIBRATED`, `Mode: PROCESS_LIMITS`, `Coverage Ratio`, `Equiv Diameter`, `Physical Diameter`.
- **Known Saved-Case Presentation Limitation:**
  Observe that `frontend/components/diagnosis/ImageAnalysis.tsx` currently renders the legacy top-level fields (representing the first configured ROI) rather than iterating through the full `region_evidence` array. This is a known, documented presentation limitation of the saved-case page; the underlying PostgreSQL database and case report preserve all affected sites losslessly.

### Step 6: Download & Inspect PDF Case Report
- Navigate to `/reports` or fetch the report endpoint directly:
  `GET http://127.0.0.1:8000/api/v1/cases/{case_id}/report.pdf`
- **Verify PDF Headers & Content:**
  - Content-Type: `application/pdf`.
  - Content-Disposition: `attachment; filename="dispenselens-case-{case_id}-r1.pdf"`.
  - Section **8. Image Inspection Evidence**: Lists observation count, affected site IDs (`dot-1`), applied limit configuration snapshot, and per-region measurements table.

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
| **Frontend Upload Workbench** | Implemented (DLK-M3-041) | CDP browser suite (12 scenarios) | Ready for interactive demos | Responsive SVG overlay locked to image content across zoom and aspect ratios. |
| **Saved-Case Multi-Site Display** | **Deferred** (Phase 4 gap) | None (legacy single-site fallback) | Limited display on saved case | `ImageAnalysis.tsx` displays legacy first-site metadata; full multi-site card deferred. |
| **Partial Score-Bearing Evidence** | **Deferred** (Phase 1 gap) | Negative tests (zero obs on partial) | Conservative fail-safe | Partially unassessed calibrated images emit 0 score-bearing observations. |
| **Reusable Profiles & Auto-Alignment** | **Deferred** (Phase 3) | None | Not implemented | Manual ROI configuration required per upload; no layout library. |
| **Industrial Dispensing Accuracy** | **Unmeasured** (Phase 5 gap) | Synthetic benchmark only | **Not ready for production** | No held-out factory dataset, lighting variation tests, or agreed acceptance metrics. |

---

## 5. Documented Limitations and Operational Notes

1. **Saved-Case Frontend Display Limitation:**
   The upload and studio workbench (`ImageUpload.tsx`) provides full multi-site interactive inspection. However, the saved case page (`/diagnosis/[id]/analysis` via `ImageAnalysis.tsx`) currently renders the legacy top-level metadata fields. Full multi-site card presentation on the saved-case page is deferred to Phase 4.
2. **Conservative Quality Gating (No Partial Evidence):**
   If any expected ROI is UNASSESSED in a calibrated image, the system marks the analysis `UNRELIABLE` and emits exactly **zero** score-bearing observations. While per-region measurements are shown in the workbench for technician visibility, the diagnostic engine conservatively refuses to score incomplete evidence.
3. **No Original Image Retention:**
   The platform intentionally does **not** persist raw image files to disk or database. Only resolution-independent normalized geometries, contours, and scalar measurements are stored.
4. **Visual PDF Inspection Tooling:**
   Automated integration tests and scripts parse PDF structure and text using `pypdf`. Headless rasterizers (`pdftoppm`, `mutool`) were not installed in the Windows environment, so visual layout/rendering checks rely on manual browser inspection.
5. **Synthetic vs. Industrial Data:**
   The offline benchmark (`backend/tests/vision_inspection_baseline.py`) verifies algorithmic repeatability against labeled synthetic fixtures. Field deployment requires team decisions regarding labeled factory image capture, optical lighting controls, and target accuracy thresholds.
