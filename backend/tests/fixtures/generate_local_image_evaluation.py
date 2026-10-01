"""
Dispense Lens - Synthetic Local Image Evaluation Dataset Generator

Generates a self-contained synthetic sample image dataset and Manifest v1 in a
user-selected directory for demonstrating and verifying the offline evaluation runner.

Includes:
- Detected, confirmed missing, unassessed, and mixed two-site cases.
- Both process-limit and reference-image comparison modes.
- At least one intentionally unlabeled site within a multi-site case.
- Optional flags to generate an all-unlabeled manifest and a corrupt image case.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import cv2
import numpy as np

from app.schemas.image import (
    AnalysisProfile,
    ImageAnalysisMode,
    NormalizedROI,
    ProcessLimits,
    ReferenceLimits,
    RoiInspectionStatus,
)
from tests.fixtures.synthetic_images import (
    create_blank_image,
    create_centered_dot_image,
    create_empty_image,
    create_multi_roi_image,
    encode_image,
)


def generate_synthetic_dataset(
    output_dir: Path,
    all_unlabeled: bool = False,
    include_corrupt: bool = False,
) -> Path:
    """Generate sample images and write a corresponding manifest.json into output_dir.

    Returns the path to the written manifest JSON file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # 1. Case 01: Clean centered deposit
    c1_bytes = create_centered_dot_image(size=200, dot_radius=25)
    (images_dir / "case_01_detected.png").write_bytes(c1_bytes)

    # 2. Case 02: Confirmed missing deposit with background fiducials
    c2_bytes = create_empty_image(size=200)
    (images_dir / "case_02_missing.png").write_bytes(c2_bytes)

    # 3. Case 03: Flat uniform image without background basis (UNASSESSED)
    c3_bytes = encode_image(create_blank_image(200, 200, bg_color=128))
    (images_dir / "case_03_unassessed.png").write_bytes(c3_bytes)

    # 4. Case 04: Two-site image (site 1 detected, site 2 unlabeled)
    # 400x200 image with a deposit at (100, 100, r=20) and blank at (300, 100)
    c4_bytes = create_multi_roi_image(
        width=400,
        height=200,
        deposits=[(100, 100, 20)],
    )
    (images_dir / "case_04_mixed.png").write_bytes(c4_bytes)

    # 5. Case 05: Reference image comparison mode
    # Current image has dot r=25, reference image has dot r=25
    c5_curr_bytes = create_centered_dot_image(size=200, dot_radius=25)
    c5_ref_bytes = create_centered_dot_image(size=200, dot_radius=25)
    (images_dir / "case_05_reference_current.png").write_bytes(c5_curr_bytes)
    (images_dir / "case_05_reference_ref.png").write_bytes(c5_ref_bytes)

    # Assemble Manifest Cases
    cases: list[dict[str, Any]] = [
        {
            "case_id": "case_01_clean_detected",
            "description": "Single-ROI clean centered deposit with process limits",
            "current_image_path": "images/case_01_detected.png",
            "reference_image_path": None,
            "profile": {
                "mode": "PROCESS_LIMITS",
                "rois": [
                    {"roi_id": "dot-1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}
                ],
                "process_limits": {
                    "min_coverage_ratio": 0.05,
                    "max_overflow_ratio": 0.05,
                },
            },
            "expected_statuses": None if all_unlabeled else {"dot-1": "DETECTED"},
            "label_provenance": "Synthetic generation fixture; ground-truth deposit constructed at center.",
            "notes": "Standard synthetic verification case.",
        },
        {
            "case_id": "case_02_confirmed_missing",
            "description": "Single-ROI confirmed missing deposit with visible background context",
            "current_image_path": "images/case_02_missing.png",
            "reference_image_path": None,
            "profile": {
                "mode": "PROCESS_LIMITS",
                "rois": [
                    {"roi_id": "dot-1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}
                ],
                "process_limits": {
                    "min_coverage_ratio": 0.05,
                },
            },
            "expected_statuses": None if all_unlabeled else {"dot-1": "MISSING"},
            "label_provenance": "Synthetic empty image with fiducial context.",
            "notes": "Expects clean MISSING status without unassessed abstention.",
        },
        {
            "case_id": "case_03_uniform_unassessed",
            "description": "Single-ROI uniform flat image triggering unassessed abstention",
            "current_image_path": "images/case_03_unassessed.png",
            "reference_image_path": None,
            "profile": {
                "mode": "PROCESS_LIMITS",
                "rois": [
                    {"roi_id": "dot-1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}
                ],
                "process_limits": {
                    "min_coverage_ratio": 0.05,
                },
            },
            "expected_statuses": None if all_unlabeled else {"dot-1": "UNASSESSED"},
            "label_provenance": "Synthetic uniform flat background.",
            "notes": "Expects UNASSESSED status due to low contrast and absence of background basis.",
        },
        {
            "case_id": "case_04_mixed_two_site",
            "description": "Two-site image with detected deposit at site 1 and intentionally unlabeled site 2",
            "current_image_path": "images/case_04_mixed.png",
            "reference_image_path": None,
            "profile": {
                "mode": "PROCESS_LIMITS",
                "rois": [
                    {"roi_id": "dot-1", "x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0},
                    {"roi_id": "dot-2", "x": 0.5, "y": 0.0, "width": 0.5, "height": 1.0},
                ],
                "process_limits": {
                    "min_coverage_ratio": 0.01,
                },
            },
            # Intentionally only label dot-1; dot-2 is omitted from expected_statuses!
            "expected_statuses": None if all_unlabeled else {"dot-1": "DETECTED"},
            "label_provenance": "dot-1 has synthetic ground-truth; dot-2 left intentionally unlabeled.",
            "notes": "Demonstrates honest accounting where unlabeled sites do not count toward accuracy.",
        },
        {
            "case_id": "case_05_reference_comparison",
            "description": "Reference-image comparison mode comparing current against reference",
            "current_image_path": "images/case_05_reference_current.png",
            "reference_image_path": "images/case_05_reference_ref.png",
            "profile": {
                "mode": "REFERENCE_IMAGE",
                "rois": [
                    {"roi_id": "ref-dot", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}
                ],
                "reference_limits": {
                    "tolerance_ratio": 0.20,
                },
            },
            "expected_statuses": None if all_unlabeled else {"ref-dot": "DETECTED"},
            "label_provenance": "Matched synthetic dot pair with identical dimensions.",
            "notes": "Exercises REFERENCE_IMAGE mode with dual image inputs.",
        },
    ]

    # Optional corrupt image case
    if include_corrupt:
        corrupt_bytes = b"\x89PNG\r\n\x1a\nCORRUPTED_TRUNCATED_DATA_NON_IMAGE"
        (images_dir / "case_06_corrupt.png").write_bytes(corrupt_bytes)
        cases.append({
            "case_id": "case_06_corrupt_image",
            "description": "Corrupt/truncated image to test error containment and runner continuation",
            "current_image_path": "images/case_06_corrupt.png",
            "reference_image_path": None,
            "profile": {
                "mode": "PROCESS_LIMITS",
                "rois": [
                    {"roi_id": "dot-1", "x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}
                ],
                "process_limits": {
                    "min_coverage_ratio": 0.05,
                },
            },
            "expected_statuses": None if all_unlabeled else {"dot-1": "DETECTED"},
            "label_provenance": "Intentionally corrupt payload for error-handling verification.",
            "notes": "Runner must catch decode error, record case failure, and continue remaining cases.",
        })

    dataset_id = "synthetic_sample_unlabeled" if all_unlabeled else "synthetic_sample_v1"
    manifest: dict[str, Any] = {
        "manifest_version": "v1",
        "dataset_id": dataset_id,
        "origin": "synthetic",
        "description": "Synthetic multi-scenario demonstration dataset for local evaluation runner.",
        "label_provenance": (
            "No ground-truth labels provided (unlabeled dataset)."
            if all_unlabeled
            else "Generated via Dispense Lens deterministic synthetic image fixtures."
        ),
        "cases": cases,
    }

    manifest_filename = "manifest_unlabeled.json" if all_unlabeled else "manifest.json"
    manifest_path = output_dir / manifest_filename
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="generate_local_image_evaluation",
        description="Generates synthetic image fixtures and a versioned manifest in a target directory.",
    )
    parser.add_argument(
        "-o", "--output-dir",
        required=True,
        type=Path,
        help="Target directory where generated images and manifest.json will be saved.",
    )
    parser.add_argument(
        "--all-unlabeled",
        action="store_true",
        default=False,
        help="Generate an all-unlabeled manifest with no expected status labels.",
    )
    parser.add_argument(
        "--include-corrupt",
        action="store_true",
        default=False,
        help="Include an intentionally corrupt image case to test partial-run error containment.",
    )

    args = parser.parse_args()
    try:
        manifest_path = generate_synthetic_dataset(
            output_dir=args.output_dir.resolve(),
            all_unlabeled=args.all_unlabeled,
            include_corrupt=args.include_corrupt,
        )
        sys.stdout.write(
            f"Successfully generated synthetic dataset:\n"
            f"  Directory: {args.output_dir.resolve()}\n"
            f"  Manifest:  {manifest_path}\n"
        )
        return 0
    except Exception as exc:
        sys.stderr.write(f"Error generating synthetic dataset: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
