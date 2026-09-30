"""
Dispense Lens - Synthetic Region Inspection Baseline Unit Tests

Verifies:
- Evaluator metric calculations independently of OpenCV segmentation pipeline.
- Confusion matrix accounting across DETECTED, MISSING, UNASSESSED.
- Abstention rate and false-missing safety rate.
- Outline availability and omission accounting.
- Mask IoU computation, coordinate scaling, and safe zero-denominator handling.
- Real runner smoke test verifying schema, non-empty case coverage, and conservative mixed gating.
"""

from __future__ import annotations

import json
import pytest
import numpy as np

from tests.vision_inspection_baseline import (
    compute_baseline_metrics,
    compute_confusion_counts,
    compute_mask_iou,
    rasterize_normalized_polygon,
    run_vision_inspection_baseline,
)


def test_compute_confusion_counts_and_accuracy() -> None:
    """Confusion matrix counts every expected/predicted pair and computes status accuracy."""
    predictions = [
        {"expected_status": "DETECTED", "predicted_status": "DETECTED"},
        {"expected_status": "DETECTED", "predicted_status": "DETECTED"},
        {"expected_status": "MISSING", "predicted_status": "MISSING"},
        {"expected_status": "UNASSESSED", "predicted_status": "UNASSESSED"},
        {"expected_status": "DETECTED", "predicted_status": "UNASSESSED"},  # Deliberate mismatch
    ]
    matrix = compute_confusion_counts(predictions)

    assert matrix["DETECTED"]["DETECTED"] == 2
    assert matrix["DETECTED"]["UNASSESSED"] == 1
    assert matrix["DETECTED"]["MISSING"] == 0
    assert matrix["MISSING"]["MISSING"] == 1
    assert matrix["UNASSESSED"]["UNASSESSED"] == 1

    metrics = compute_baseline_metrics(predictions, iou_records=[])
    acc = metrics["status_accuracy"]
    assert acc["numerator"] == 4
    assert acc["denominator"] == 5
    assert acc["rate"] == 0.8


def test_abstention_and_false_missing_metrics() -> None:
    """Evaluator tracks abstentions and penalizes UNASSESSED sites misclassified as MISSING."""
    predictions = [
        {"expected_status": "UNASSESSED", "predicted_status": "UNASSESSED"},
        {"expected_status": "UNASSESSED", "predicted_status": "MISSING"},  # Deliberate false missing
        {"expected_status": "DETECTED", "predicted_status": "DETECTED"},
    ]
    metrics = compute_baseline_metrics(predictions, iou_records=[])

    # Abstention: 1 predicted unassessed out of 3 total sites
    abst = metrics["abstention_rate"]
    assert abst["numerator"] == 1
    assert abst["denominator"] == 3
    assert abst["rate"] == pytest.approx(1 / 3, abs=1e-4)

    # False missing: 1 false missing out of 2 expected unassessed sites
    fm = metrics["false_missing_rate"]
    assert fm["numerator"] == 1
    assert fm["denominator"] == 2
    assert fm["rate"] == 0.5


def test_outline_availability_and_omission() -> None:
    """Evaluator reports outline availability rate and omission counts among detected sites with masks."""
    predictions = [
        {
            "expected_status": "DETECTED",
            "predicted_status": "DETECTED",
            "has_gt_mask": True,
            "has_outline": True,
        },
        {
            "expected_status": "DETECTED",
            "predicted_status": "DETECTED",
            "has_gt_mask": True,
            "has_outline": False,  # Omitted outline
        },
        {
            "expected_status": "MISSING",
            "predicted_status": "MISSING",
            "has_gt_mask": False,
            "has_outline": False,
        },
    ]
    metrics = compute_baseline_metrics(predictions, iou_records=[])
    oa = metrics["outline_availability_rate"]

    assert oa["numerator"] == 1
    assert oa["denominator"] == 2
    assert oa["omitted_count"] == 1
    assert oa["rate"] == 0.5


def test_mask_iou_and_empty_denominator() -> None:
    """IoU computes exact overlap math and handles zero-denominator cases without ZeroDivisionError."""
    # 1. Empty denominator handling
    empty_metrics = compute_baseline_metrics([], iou_records=[])
    iou_empty = empty_metrics["mean_outline_iou"]
    assert iou_empty["numerator"] == 0.0
    assert iou_empty["denominator"] == 0
    assert iou_empty["mean"] is None

    # 2. Known geometric overlap math
    mask_a = np.zeros((100, 100), dtype=np.uint8)
    mask_a[20:60, 20:60] = 255  # Area = 40 * 40 = 1600

    mask_b = np.zeros((100, 100), dtype=np.uint8)
    mask_b[20:60, 20:60] = 255  # Identical

    assert compute_mask_iou(mask_a, mask_b) == 1.0

    mask_c = np.zeros((100, 100), dtype=np.uint8)
    mask_c[20:60, 40:80] = 255  # Overlaps horizontally across x=[40..60] (20 cols, 40 rows = 800)
    # Intersection = 800, Union = 1600 + 1600 - 800 = 2400 -> IoU = 800 / 2400 = 1/3
    assert compute_mask_iou(mask_a, mask_c) == pytest.approx(1 / 3, abs=1e-5)

    # 3. Disjoint masks
    mask_d = np.zeros((100, 100), dtype=np.uint8)
    mask_d[70:90, 70:90] = 255
    assert compute_mask_iou(mask_a, mask_d) == 0.0

    # 4. Both zero masks
    zero_1 = np.zeros((50, 50), dtype=np.uint8)
    zero_2 = np.zeros((50, 50), dtype=np.uint8)
    assert compute_mask_iou(zero_1, zero_2) == 0.0

    # 5. Mismatched shapes raise ValueError
    with pytest.raises(ValueError, match="shapes do not match"):
        compute_mask_iou(mask_a, zero_1)


def test_rasterize_normalized_polygon() -> None:
    """Rasterizing normalized polygon yields full-image binary mask matching pixel dimensions."""
    # 100x100 image, polygon box from [0.2, 0.2] to [0.8, 0.8] -> [20..80, 20..80]
    polygon = [
        {"x": 0.2, "y": 0.2},
        {"x": 0.8, "y": 0.2},
        {"x": 0.8, "y": 0.8},
        {"x": 0.2, "y": 0.8},
    ]
    mask = rasterize_normalized_polygon(polygon, 100, 100)
    assert mask.shape == (100, 100)
    assert mask.dtype == np.uint8
    # Center pixel is inside polygon
    assert mask[50, 50] == 255
    # Corner pixel is outside polygon
    assert mask[5, 5] == 0

    # Degenerate polygons (fewer than 3 points) return all-zero mask
    empty_mask = rasterize_normalized_polygon([], 100, 100)
    assert int(empty_mask.sum()) == 0


def test_real_runner_smoke_test() -> None:
    """Real runner executes offline baseline against manifest, preserving gates and valid JSON output."""
    report = run_vision_inspection_baseline()

    # Structural contract checks
    assert report["manifest_name"] == "synthetic_region_inspection_baseline_v1"
    assert report["case_count"] == 6
    assert report["total_expected_sites"] == 9
    assert report["elapsed_seconds"] > 0

    # Check metrics existence
    metrics = report["metrics"]
    assert "status_accuracy" in metrics
    assert "abstention_rate" in metrics
    assert "false_missing_rate" in metrics
    assert "outline_availability_rate" in metrics
    assert "mean_outline_iou" in metrics
    assert metrics["status_accuracy"]["denominator"] == 9

    # Verify conservative mixed-image gating is preserved in Case 4
    case4 = next(c for c in report["cases"] if c["case_id"] == "case_04_mixed_detected_unassessed")
    assert case4["overall_status"] == "UNRELIABLE"
    assert case4["inspection_coverage_status"] == "PARTIAL"

    # Verify JSON serializability
    dumped = json.dumps(report)
    assert len(dumped) > 100
