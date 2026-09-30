"""
Dispense Lens - Synthetic Region Inspection Baseline Runner

Provides an offline, deterministic evaluation of the region inspection pipeline
across a fixed synthetic fixture manifest. Computes status confusion counts,
accuracy, abstention rate, false-missing safety rate, outline availability, and
mean IoU against construction-grounded masks without database, network, or server dependencies.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path for direct module execution
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import cv2
import numpy as np

from app.api.images import _sync_analyze_image
from app.schemas.image import (
    AnalysisProfile,
    ImageAnalysisMode,
    NormalizedPoint,
    NormalizedROI,
    ProcessLimits,
    RoiInspectionStatus,
)
from tests.fixtures.synthetic_images import (
    create_blank_image,
    create_centered_dot_image,
    create_empty_image,
    create_mixed_detected_and_missing_image,
    create_mixed_detected_and_unassessed_image,
    create_multi_roi_image,
    encode_image,
)


@dataclass
class SyntheticFixtureCase:
    """Deterministic synthetic test fixture with ground-truth expectations."""

    case_id: str
    description: str
    image_bytes: bytes
    width: int
    height: int
    profile: AnalysisProfile
    expected_statuses: dict[str, RoiInspectionStatus]
    ground_truth_masks: dict[str, np.ndarray | None]


def rasterize_normalized_polygon(
    polygon: list[NormalizedPoint] | list[dict[str, float]],
    width: int,
    height: int,
) -> np.ndarray:
    """Rasterize a list of normalized coordinates into a full-image binary mask."""
    mask = np.zeros((height, width), dtype=np.uint8)
    if not polygon or len(polygon) < 3:
        return mask

    pts: list[list[int]] = []
    for pt in polygon:
        x = pt.x if hasattr(pt, "x") else pt["x"]
        y = pt.y if hasattr(pt, "y") else pt["y"]
        px = int(round(x * width))
        py = int(round(y * height))
        pts.append([px, py])

    pts_arr = np.array(pts, dtype=np.int32)
    cv2.fillPoly(mask, [pts_arr], 255)
    return mask


def compute_mask_iou(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    """Compute Intersection-over-Union (IoU) between two binary masks."""
    if mask_a.shape != mask_b.shape:
        raise ValueError(f"Mask shapes do not match: {mask_a.shape} vs {mask_b.shape}")

    intersection = int(np.logical_and(mask_a > 0, mask_b > 0).sum())
    union = int(np.logical_or(mask_a > 0, mask_b > 0).sum())
    if union == 0:
        return 0.0
    return float(intersection) / float(union)


def compute_confusion_counts(
    predictions: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Build a 3x3 confusion matrix across DETECTED, MISSING, and UNASSESSED statuses."""
    statuses = ["DETECTED", "MISSING", "UNASSESSED"]
    matrix: dict[str, dict[str, int]] = {exp: {pred: 0 for pred in statuses} for exp in statuses}
    for p in predictions:
        exp = p["expected_status"]
        pred = p["predicted_status"]
        if exp in matrix and pred in matrix[exp]:
            matrix[exp][pred] += 1
    return matrix


def compute_baseline_metrics(
    predictions: list[dict[str, Any]],
    iou_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute transparent evaluation metrics with explicit numerators and denominators."""
    total_sites = len(predictions)
    correct_status = sum(1 for p in predictions if p["expected_status"] == p["predicted_status"])

    pred_unassessed = sum(1 for p in predictions if p["predicted_status"] == "UNASSESSED")
    exp_unassessed = sum(1 for p in predictions if p["expected_status"] == "UNASSESSED")

    # Safety metric: expected UNASSESSED falsely categorized as MISSING
    false_missing = sum(
        1
        for p in predictions
        if p["expected_status"] == "UNASSESSED" and p["predicted_status"] == "MISSING"
    )

    # Outline availability among detected sites with known ground-truth masks
    detected_with_mask = sum(
        1
        for p in predictions
        if p["expected_status"] == "DETECTED" and p.get("has_gt_mask", False)
    )
    outlines_present = sum(
        1
        for p in predictions
        if p["expected_status"] == "DETECTED"
        and p.get("has_gt_mask", False)
        and p.get("has_outline", False)
    )
    outlines_omitted = detected_with_mask - outlines_present

    # Mean polygon-mask IoU
    iou_count = len(iou_records)
    sum_iou = sum(r["iou"] for r in iou_records)
    mean_iou = (sum_iou / iou_count) if iou_count > 0 else None

    return {
        "status_accuracy": {
            "numerator": correct_status,
            "denominator": total_sites,
            "rate": round(correct_status / total_sites, 4) if total_sites > 0 else 0.0,
        },
        "abstention_rate": {
            "numerator": pred_unassessed,
            "denominator": total_sites,
            "rate": round(pred_unassessed / total_sites, 4) if total_sites > 0 else 0.0,
        },
        "false_missing_rate": {
            "numerator": false_missing,
            "denominator": exp_unassessed,
            "rate": round(false_missing / exp_unassessed, 4) if exp_unassessed > 0 else 0.0,
        },
        "outline_availability_rate": {
            "numerator": outlines_present,
            "denominator": detected_with_mask,
            "omitted_count": outlines_omitted,
            "rate": round(outlines_present / detected_with_mask, 4) if detected_with_mask > 0 else 0.0,
        },
        "mean_outline_iou": {
            "numerator": round(sum_iou, 4) if iou_count > 0 else 0.0,
            "denominator": iou_count,
            "mean": round(mean_iou, 4) if mean_iou is not None else None,
        },
    }


def get_synthetic_fixture_manifest() -> list[SyntheticFixtureCase]:
    """Build the fixed, deterministic synthetic fixture manifest for region inspection."""
    cases: list[SyntheticFixtureCase] = []

    # Case 1: Clean detected dot in single ROI
    w1, h1 = 200, 200
    img1_bytes = create_centered_dot_image(size=200, dot_radius=25)
    mask1 = np.zeros((h1, w1), dtype=np.uint8)
    cv2.circle(mask1, (w1 // 2, h1 // 2), 25, 255, -1)
    cases.append(
        SyntheticFixtureCase(
            case_id="case_01_clean_detected_dot",
            description="Clean circular deposit centered in single ROI",
            image_bytes=img1_bytes,
            width=w1,
            height=h1,
            profile=AnalysisProfile(
                mode=ImageAnalysisMode.PROCESS_LIMITS,
                rois=[NormalizedROI(roi_id="r1", x=0.25, y=0.25, width=0.5, height=0.5)],
                process_limits=ProcessLimits(min_coverage_ratio=0.05),
            ),
            expected_statuses={"r1": RoiInspectionStatus.DETECTED},
            ground_truth_masks={"r1": mask1},
        )
    )

    # Case 2: Confirmed missing expected site with background fiducials
    w2, h2 = 200, 200
    img2_bytes = create_empty_image(size=200)
    cases.append(
        SyntheticFixtureCase(
            case_id="case_02_confirmed_missing",
            description="Confirmed missing site with established background fiducial context",
            image_bytes=img2_bytes,
            width=w2,
            height=h2,
            profile=AnalysisProfile(
                mode=ImageAnalysisMode.PROCESS_LIMITS,
                rois=[NormalizedROI(roi_id="r1", x=0.25, y=0.25, width=0.5, height=0.5)],
                process_limits=ProcessLimits(min_coverage_ratio=0.05),
            ),
            expected_statuses={"r1": RoiInspectionStatus.MISSING},
            ground_truth_masks={"r1": None},
        )
    )

    # Case 3: Uniform flat unassessed site
    w3, h3 = 200, 200
    img3_bytes = encode_image(create_blank_image(w3, h3, bg_color=128))
    cases.append(
        SyntheticFixtureCase(
            case_id="case_03_uniform_unassessed",
            description="Uniform low-contrast image without background basis; unassessed inspection",
            image_bytes=img3_bytes,
            width=w3,
            height=h3,
            profile=AnalysisProfile(
                mode=ImageAnalysisMode.PROCESS_LIMITS,
                rois=[NormalizedROI(roi_id="r1", x=0.25, y=0.25, width=0.5, height=0.5)],
                process_limits=ProcessLimits(min_coverage_ratio=0.05),
            ),
            expected_statuses={"r1": RoiInspectionStatus.UNASSESSED},
            ground_truth_masks={"r1": None},
        )
    )

    # Case 4: Mixed detected and unassessed two-site image
    w4, h4 = 400, 200
    img4_bytes = create_mixed_detected_and_unassessed_image(
        width=w4, height=h4, dot_cx=100, dot_cy=100, dot_radius=20
    )
    mask4_r_det = np.zeros((h4, w4), dtype=np.uint8)
    cv2.circle(mask4_r_det, (100, 100), 20, 255, -1)
    cases.append(
        SyntheticFixtureCase(
            case_id="case_04_mixed_detected_unassessed",
            description="Two-site image with detected deposit at site 1 and flat unassessed site 2",
            image_bytes=img4_bytes,
            width=w4,
            height=h4,
            profile=AnalysisProfile(
                mode=ImageAnalysisMode.PROCESS_LIMITS,
                rois=[
                    NormalizedROI(roi_id="r_detected", x=0.125, y=0.25, width=0.25, height=0.5),
                    NormalizedROI(roi_id="r_unassessed", x=0.625, y=0.25, width=0.25, height=0.5),
                ],
                process_limits=ProcessLimits(min_coverage_ratio=0.05),
            ),
            expected_statuses={
                "r_detected": RoiInspectionStatus.DETECTED,
                "r_unassessed": RoiInspectionStatus.UNASSESSED,
            },
            ground_truth_masks={
                "r_detected": mask4_r_det,
                "r_unassessed": None,
            },
        )
    )

    # Case 5: Two-site image with all sites detected
    w5, h5 = 400, 200
    img5_bytes = create_multi_roi_image(w5, h5, deposits=[(100, 100, 20), (300, 100, 20)])
    mask5_r1 = np.zeros((h5, w5), dtype=np.uint8)
    cv2.circle(mask5_r1, (100, 100), 20, 255, -1)
    mask5_r2 = np.zeros((h5, w5), dtype=np.uint8)
    cv2.circle(mask5_r2, (300, 100), 20, 255, -1)
    cases.append(
        SyntheticFixtureCase(
            case_id="case_05_two_site_detected",
            description="Two-site image with both dispensing sites reliably detected",
            image_bytes=img5_bytes,
            width=w5,
            height=h5,
            profile=AnalysisProfile(
                mode=ImageAnalysisMode.PROCESS_LIMITS,
                rois=[
                    NormalizedROI(roi_id="r1", x=0.125, y=0.25, width=0.25, height=0.5),
                    NormalizedROI(roi_id="r2", x=0.625, y=0.25, width=0.25, height=0.5),
                ],
                process_limits=ProcessLimits(min_coverage_ratio=0.05),
            ),
            expected_statuses={
                "r1": RoiInspectionStatus.DETECTED,
                "r2": RoiInspectionStatus.DETECTED,
            },
            ground_truth_masks={
                "r1": mask5_r1,
                "r2": mask5_r2,
            },
        )
    )

    # Case 6: Mixed detected and confirmed missing two-site image
    w6, h6 = 400, 200
    img6_bytes = create_mixed_detected_and_missing_image(
        width=w6, height=h6, dot_cx=100, dot_cy=100, dot_radius=20
    )
    mask6_r_det = np.zeros((h6, w6), dtype=np.uint8)
    cv2.circle(mask6_r_det, (100, 100), 20, 255, -1)
    cases.append(
        SyntheticFixtureCase(
            case_id="case_06_mixed_detected_missing",
            description="Two-site image with detected deposit at site 1 and confirmed missing deposit at site 2",
            image_bytes=img6_bytes,
            width=w6,
            height=h6,
            profile=AnalysisProfile(
                mode=ImageAnalysisMode.PROCESS_LIMITS,
                rois=[
                    NormalizedROI(roi_id="r_detected", x=0.125, y=0.25, width=0.25, height=0.5),
                    NormalizedROI(roi_id="r_missing", x=0.625, y=0.25, width=0.25, height=0.5),
                ],
                process_limits=ProcessLimits(min_coverage_ratio=0.05),
            ),
            expected_statuses={
                "r_detected": RoiInspectionStatus.DETECTED,
                "r_missing": RoiInspectionStatus.MISSING,
            },
            ground_truth_masks={
                "r_detected": mask6_r_det,
                "r_missing": None,
            },
        )
    )

    return cases


def run_vision_inspection_baseline(
    manifest: list[SyntheticFixtureCase] | None = None,
) -> dict[str, Any]:
    """Execute the offline evaluation pipeline against the synthetic fixture manifest.

    Timing note:
    Each case in ``cases`` reports descriptive ``elapsed_seconds`` measuring the wall-clock
    analysis execution time of ``_sync_analyze_image`` for that fixture. The top-level
    ``elapsed_seconds`` measures total manifest execution. Both are descriptive metrics
    and must not be interpreted as performance targets.
    """
    if manifest is None:
        manifest = get_synthetic_fixture_manifest()

    start_time = time.perf_counter()
    per_case_results: list[dict[str, Any]] = []
    site_predictions: list[dict[str, Any]] = []
    iou_records: list[dict[str, Any]] = []

    for case in manifest:
        case_start = time.perf_counter()
        resp = _sync_analyze_image(case.image_bytes, case.profile)
        case_elapsed = time.perf_counter() - case_start
        meas_by_id = {m.roi_id: m for m in resp.roi_measurements}

        case_sites: list[dict[str, Any]] = []
        for roi in case.profile.rois:
            roi_id = roi.roi_id
            meas = meas_by_id.get(roi_id)
            pred_status = meas.inspection_status if meas else RoiInspectionStatus.UNASSESSED
            exp_status = case.expected_statuses[roi_id]

            gt_mask = case.ground_truth_masks.get(roi_id)
            has_gt_mask = gt_mask is not None
            has_outline = (
                meas is not None
                and meas.deposit_outline_normalized is not None
                and len(meas.deposit_outline_normalized) >= 3
            )

            iou_val: float | None = None
            if has_gt_mask and has_outline and meas is not None and meas.deposit_outline_normalized:
                pred_mask = rasterize_normalized_polygon(
                    meas.deposit_outline_normalized, case.width, case.height
                )
                iou_val = compute_mask_iou(pred_mask, gt_mask)
                iou_records.append({
                    "case_id": case.case_id,
                    "roi_id": roi_id,
                    "iou": iou_val,
                })

            prediction_item = {
                "case_id": case.case_id,
                "roi_id": roi_id,
                "expected_status": exp_status.value,
                "predicted_status": pred_status.value,
                "status_match": exp_status.value == pred_status.value,
                "has_gt_mask": has_gt_mask,
                "has_outline": has_outline,
                "outline_iou": round(iou_val, 4) if iou_val is not None else None,
                "warnings": meas.inspection_warnings if meas else ["Missing measurement data."],
            }
            site_predictions.append(prediction_item)
            case_sites.append(prediction_item)

        per_case_results.append({
            "case_id": case.case_id,
            "description": case.description,
            "elapsed_seconds": round(case_elapsed, 4),
            "overall_status": resp.status.value,
            "inspection_coverage_status": (
                resp.aggregate_measurements.inspection_coverage_status.value
                if resp.aggregate_measurements.inspection_coverage_status
                else None
            ),
            "expected_roi_count": len(case.profile.rois),
            "assessed_roi_count": resp.aggregate_measurements.assessed_roi_count,
            "sites": case_sites,
            "case_warnings": resp.warnings,
        })

    elapsed = time.perf_counter() - start_time
    confusion = compute_confusion_counts(site_predictions)
    metrics = compute_baseline_metrics(site_predictions, iou_records)

    return {
        "manifest_name": "synthetic_region_inspection_baseline_v1",
        "case_count": len(manifest),
        "total_expected_sites": len(site_predictions),
        "elapsed_seconds": round(elapsed, 4),
        "confusion_matrix": confusion,
        "metrics": metrics,
        "cases": per_case_results,
    }


def main() -> None:
    """CLI entry point for running the synthetic region-inspection baseline."""
    try:
        report = run_vision_inspection_baseline()
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        sys.exit(0)
    except Exception as exc:
        sys.stderr.write(f"Error executing vision inspection baseline: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
