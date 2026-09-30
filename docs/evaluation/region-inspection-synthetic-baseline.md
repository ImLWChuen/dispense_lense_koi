# Synthetic Region-Inspection Baseline Report

Date: 2026-09-30
Task: `DLK-M3-038`
Evaluation Manifest: `synthetic_region_inspection_baseline_v1`
Scope: Offline, deterministic evaluation of the DispenseLens region-inspection computer vision pipeline on synthetic fixtures.

---

## 1. Executive Summary

This document establishes an honest, repeatable, offline baseline for the region inspection computer vision pipeline (`backend/app/api/images.py` `_sync_analyze_image`, `backend/app/services/vision/segmentation.py`, `backend/app/services/vision/measurement.py`, and `backend/app/services/vision/overlay.py`).

The evaluation runs against a fixed, 6-case synthetic manifest with 9 labeled expected dispensing sites. Across this benchmark:
- **Status Accuracy:** 9/9 (100%) across labeled expected sites.
- **Abstention Rate:** 2/9 (22.2%) properly abstained as `UNASSESSED`.
- **False-Missing Safety Rate:** 0/2 (0.0%) unassessed sites were falsely reported as missing deposits.
- **Outline Availability Rate:** 5/5 (100%) among detected sites with known masks.
- **Mean Outline IoU:** 0.9970 across 5 detected sites evaluated against construction-grounded circular masks.
- **Conservative Gating:** Multi-site images with unassessed regions (`case_04`) strictly enforced overall `UNRELIABLE` status and `PARTIAL` coverage, emitting zero score-bearing observations.

> [!WARNING]
> **Limits of Synthetic Evidence:**
> These metrics demonstrate algorithmic correctness, coordinate mapping consistency, and conservative gating under controlled, deterministic conditions. They **do not** prove industrial accuracy, sub-millimeter precision, or defect recall on real production lines with fluctuating illumination, translucent adhesives, specular reflections, or board warping. Real-image benchmarks require physically captured PCB images and independent technician labels.

---

## 2. Fixed Fixture Manifest Specification

The manifest consists of 6 deterministic synthetic cases generated in-memory without persistent disk I/O, unseeded randomness, or external services:

| Case ID | Dimensions | Description | ROI ID | Expected Status | GT Mask Available | Construction Rationale |
|---|---|---|---|---|---|---|
| `case_01_clean_detected_dot` | 200x200 | Clean circular deposit centered in single ROI | `r1` | `DETECTED` | Yes (Circle r=25 at 100,100) | High contrast dark dot on light substrate; reliable segmentation and full polygon outline. |
| `case_02_confirmed_missing` | 200x200 | Confirmed missing site with background fiducials | `r1` | `MISSING` | No (no deposit) | Bare substrate inside target ROI with high-contrast fiducials in window margins establishing background context. |
| `case_03_uniform_unassessed` | 200x200 | Uniform flat gray low-contrast image | `r1` | `UNASSESSED` | No | Target and surroundings are both uniform gray (128); pipeline cannot distinguish empty target from sensor failure/occlusion. |
| `case_04_mixed_detected_unassessed` | 400x200 | Two-site image: detected dot + flat unassessed | `r_detected`<br>`r_unassessed` | `DETECTED`<br>`UNASSESSED` | Yes (Circle r=20 at 100,100)<br>No | Left window contains clean deposit; right window contains flat gray substrate. Tests conservative gating (`UNRELIABLE`, `PARTIAL`). |
| `case_05_two_site_detected` | 400x200 | Two-site image: two reliable dots | `r1`<br>`r2` | `DETECTED`<br>`DETECTED` | Yes (Circle r=20 at 100,100)<br>Yes (Circle r=20 at 300,100) | Multi-dot dispensing pattern with reliable segmentation across distinct regions; evaluates multi-outline alignment. |
| `case_06_mixed_detected_missing` | 400x200 | Two-site image: detected dot + confirmed missing | `r_detected`<br>`r_missing` | `DETECTED`<br>`MISSING` | Yes (Circle r=20 at 100,100)<br>No | Left window has detected deposit; right window has fiducials and confirmed missing deposit. Validates complete multi-site coverage with missing site. |

---

## 3. Supported Capture Assumptions

The pipeline and baseline evaluate images under the following operational assumptions:
1. **Camera Geometry:** Orthogonal top-down perspective (no severe parallax or perspective tilt).
2. **Region Alignment:** Target ROIs are caller-specified in normalized $[0.0, 1.0]$ coordinates and roughly centered on expected deposit positions.
3. **Substrate Context for Missing Confirmation:** Deposit absence (`MISSING`) requires visible substrate features or fiducials in the expanded analysis window margin. Flat uniform regions without contrast abstain as `UNASSESSED` to prevent false missing-deposit alarms.
4. **Deposit Contrast:** Target material exhibits identifiable bimodal or thresholdable contrast against the substrate.

---

## 4. Execution Command and Runtime Context

### Reproduction Command
From repository `backend/` directory in PowerShell:
```powershell
.\.venv\Scripts\python.exe -m tests.vision_inspection_baseline
```

Or from repository root:
```powershell
& .\backend\.venv\Scripts\python.exe backend/tests/vision_inspection_baseline.py
```

### Runtime Environment
- **Operating System:** Windows 11
- **Python Version:** Python 3.14.0 (via established virtual environment `backend/.venv`)
- **OpenCV Version:** headless `opencv-python`
- **Dependencies Required:** No database connection, no network requests, no running web server.

---

## 5. Baseline Evaluation Output (Raw Execution)

```json
{
  "manifest_name": "synthetic_region_inspection_baseline_v1",
  "case_count": 6,
  "total_expected_sites": 9,
  "elapsed_seconds": 0.0161,
  "confusion_matrix": {
    "DETECTED": {
      "DETECTED": 5,
      "MISSING": 0,
      "UNASSESSED": 0
    },
    "MISSING": {
      "DETECTED": 0,
      "MISSING": 2,
      "UNASSESSED": 0
    },
    "UNASSESSED": {
      "DETECTED": 0,
      "MISSING": 0,
      "UNASSESSED": 2
    }
  },
  "metrics": {
    "status_accuracy": {
      "numerator": 9,
      "denominator": 9,
      "rate": 1.0
    },
    "abstention_rate": {
      "numerator": 2,
      "denominator": 9,
      "rate": 0.2222
    },
    "false_missing_rate": {
      "numerator": 0,
      "denominator": 2,
      "rate": 0.0
    },
    "outline_availability_rate": {
      "numerator": 5,
      "denominator": 5,
      "omitted_count": 0,
      "rate": 1.0
    },
    "mean_outline_iou": {
      "numerator": 4.9852,
      "denominator": 5,
      "mean": 0.997
    }
  },
  "cases": [
    {
      "case_id": "case_01_clean_detected_dot",
      "description": "Clean circular deposit centered in single ROI",
      "elapsed_seconds": 0.0051,
      "overall_status": "CALIBRATED",
      "inspection_coverage_status": "COMPLETE",
      "expected_roi_count": 1,
      "assessed_roi_count": 1,
      "sites": [
        {
          "case_id": "case_01_clean_detected_dot",
          "roi_id": "r1",
          "expected_status": "DETECTED",
          "predicted_status": "DETECTED",
          "status_match": true,
          "has_gt_mask": true,
          "has_outline": true,
          "outline_iou": 0.998,
          "warnings": []
        }
      ],
      "case_warnings": []
    },
    {
      "case_id": "case_02_confirmed_missing",
      "description": "Confirmed missing site with established background fiducial context",
      "elapsed_seconds": 0.0007,
      "overall_status": "CALIBRATED",
      "inspection_coverage_status": "COMPLETE",
      "expected_roi_count": 1,
      "assessed_roi_count": 1,
      "sites": [
        {
          "case_id": "case_02_confirmed_missing",
          "roi_id": "r1",
          "expected_status": "MISSING",
          "predicted_status": "MISSING",
          "status_match": true,
          "has_gt_mask": false,
          "has_outline": false,
          "outline_iou": null,
          "warnings": [
            "No deposit detected inside target ROI; established background indicates missing deposit."
          ]
        }
      ],
      "case_warnings": [
        "Missing deposits detected in 1 ROI(s): r1."
      ]
    },
    {
      "case_id": "case_03_uniform_unassessed",
      "description": "Uniform low-contrast image without background basis; unassessed inspection",
      "elapsed_seconds": 0.0005,
      "overall_status": "UNRELIABLE",
      "inspection_coverage_status": "NONE",
      "expected_roi_count": 1,
      "assessed_roi_count": 0,
      "sites": [
        {
          "case_id": "case_03_uniform_unassessed",
          "roi_id": "r1",
          "expected_status": "UNASSESSED",
          "predicted_status": "UNASSESSED",
          "status_match": true,
          "has_gt_mask": false,
          "has_outline": false,
          "outline_iou": null,
          "warnings": [
            "Target and surroundings are both uniform; cannot establish background or missing deposit without reference.",
            "ROI 'r1' segmentation quality (0.00) is below reliable threshold."
          ]
        }
      ],
      "case_warnings": [
        "Unassessed regions detected in 1 ROI(s): r1.",
        "ROI 'r1' is unassessed (Target and surroundings are both uniform; cannot establish background or missing deposit without reference.; ROI 'r1' segmentation quality (0.00) is below reliable threshold.)."
      ]
    },
    {
      "case_id": "case_04_mixed_detected_unassessed",
      "description": "Two-site image with detected deposit at site 1 and flat unassessed site 2",
      "elapsed_seconds": 0.0023,
      "overall_status": "UNRELIABLE",
      "inspection_coverage_status": "PARTIAL",
      "expected_roi_count": 2,
      "assessed_roi_count": 1,
      "sites": [
        {
          "case_id": "case_04_mixed_detected_unassessed",
          "roi_id": "r_detected",
          "expected_status": "DETECTED",
          "predicted_status": "DETECTED",
          "status_match": true,
          "has_gt_mask": true,
          "has_outline": true,
          "outline_iou": 0.9968,
          "warnings": []
        },
        {
          "case_id": "case_04_mixed_detected_unassessed",
          "roi_id": "r_unassessed",
          "expected_status": "UNASSESSED",
          "predicted_status": "UNASSESSED",
          "status_match": true,
          "has_gt_mask": false,
          "has_outline": false,
          "outline_iou": null,
          "warnings": [
            "Target and surroundings are both uniform; cannot establish background or missing deposit without reference.",
            "ROI 'r_unassessed' segmentation quality (0.00) is below reliable threshold."
          ]
        }
      ],
      "case_warnings": [
        "Unassessed regions detected in 1 ROI(s): r_unassessed.",
        "ROI 'r_unassessed' is unassessed (Target and surroundings are both uniform; cannot establish background or missing deposit without reference.; ROI 'r_unassessed' segmentation quality (0.00) is below reliable threshold.)."
      ]
    },
    {
      "case_id": "case_05_two_site_detected",
      "description": "Two-site image with both dispensing sites reliably detected",
      "elapsed_seconds": 0.0039,
      "overall_status": "CALIBRATED",
      "inspection_coverage_status": "COMPLETE",
      "expected_roi_count": 2,
      "assessed_roi_count": 2,
      "sites": [
        {
          "case_id": "case_05_two_site_detected",
          "roi_id": "r1",
          "expected_status": "DETECTED",
          "predicted_status": "DETECTED",
          "status_match": true,
          "has_gt_mask": true,
          "has_outline": true,
          "outline_iou": 0.9968,
          "warnings": []
        },
        {
          "case_id": "case_05_two_site_detected",
          "roi_id": "r2",
          "expected_status": "DETECTED",
          "predicted_status": "DETECTED",
          "status_match": true,
          "has_gt_mask": true,
          "has_outline": true,
          "outline_iou": 0.9968,
          "warnings": []
        }
      ],
      "case_warnings": []
    },
    {
      "case_id": "case_06_mixed_detected_missing",
      "description": "Two-site image with detected deposit at site 1 and confirmed missing deposit at site 2",
      "elapsed_seconds": 0.0025,
      "overall_status": "CALIBRATED",
      "inspection_coverage_status": "COMPLETE",
      "expected_roi_count": 2,
      "assessed_roi_count": 2,
      "sites": [
        {
          "case_id": "case_06_mixed_detected_missing",
          "roi_id": "r_detected",
          "expected_status": "DETECTED",
          "predicted_status": "DETECTED",
          "status_match": true,
          "has_gt_mask": true,
          "has_outline": true,
          "outline_iou": 0.9968,
          "warnings": []
        },
        {
          "case_id": "case_06_mixed_detected_missing",
          "roi_id": "r_missing",
          "expected_status": "MISSING",
          "predicted_status": "MISSING",
          "status_match": true,
          "has_gt_mask": false,
          "has_outline": false,
          "outline_iou": null,
          "warnings": [
            "No deposit detected inside target ROI; established background indicates missing deposit."
          ]
        }
      ],
      "case_warnings": [
        "Missing deposits detected in 1 ROI(s): r_missing."
      ]
    }
  ]
}
```

---

## 6. Mismatches and Exclusions

- **Status Mismatches:** 0 mismatches across the 9 evaluated sites.
- **Outline Omissions:** 0 unexpected omissions across the 5 detected sites.
- **Exclusions:**
  - Non-detected sites (`MISSING` and `UNASSESSED`) are excluded from IoU calculations by design, as no deposit contour is published or expected.
  - No synthetic images with random unseeded noise (`create_noisy_image`) are included in the baseline to maintain strict test determinism.
