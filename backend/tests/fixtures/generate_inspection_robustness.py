"""
Dispense Lens - Synthetic Inspection Robustness Dataset Generator

Generates a deterministic 14-case synthetic image dataset and Manifest v1
evaluating manual-region inspection behavior under controlled degradation:
- Baseline clean controls (detected, confirmed missing, uniform unassessed).
- Blur at mild and heavy documented levels.
- Darker (underexposure), brighter (overexposure), and low-contrast variations.
- Bounded specular glare and severe washout glare.
- Reliable site beside degraded site.
- Clipped deposit at image boundary with explicit coordinate transform.
- Glare and blur variants on missing sites.
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
    RoiInspectionStatus,
)
from tests.fixtures.synthetic_images import encode_image
from tests.vision_inspection_dataset import DatasetManifest, DatasetOrigin, ManifestCase


# Fixed standard 400x200 two-site layout
IMAGE_WIDTH = 400
IMAGE_HEIGHT = 200

DEFAULT_ROIS = [
    NormalizedROI(roi_id="roi_1", x=0.10, y=0.20, width=0.30, height=0.60),
    NormalizedROI(roi_id="roi_2", x=0.60, y=0.20, width=0.30, height=0.60),
]

# Illustrative synthetic process limits - labeled as synthetic, not approved manufacturing tolerances
DEFAULT_PROCESS_LIMITS = ProcessLimits(
    min_coverage_ratio=0.05,
    max_coverage_ratio=0.50,
    min_circularity=0.70,
)

DEFAULT_PROFILE = AnalysisProfile(
    mode=ImageAnalysisMode.PROCESS_LIMITS,
    rois=DEFAULT_ROIS,
    process_limits=DEFAULT_PROCESS_LIMITS,
)

CLIPPED_ROIS = [
    NormalizedROI(roi_id="roi_1_clipped", x=0.0, y=0.20, width=0.1875, height=0.60),
    NormalizedROI(roi_id="roi_2_shifted", x=0.3875, y=0.20, width=0.30, height=0.60),
]

CLIPPED_PROFILE = AnalysisProfile(
    mode=ImageAnalysisMode.PROCESS_LIMITS,
    rois=CLIPPED_ROIS,
    process_limits=DEFAULT_PROCESS_LIMITS,
)


def _create_base_clean_image() -> np.ndarray:
    """Create deterministic baseline two-site substrate image with crisp circular deposits."""
    img = np.full((IMAGE_HEIGHT, IMAGE_WIDTH, 3), 245, dtype=np.uint8)
    cv2.circle(img, (100, 100), 20, (30, 30, 30), -1)
    cv2.circle(img, (300, 100), 20, (30, 30, 30), -1)
    return img


def _create_base_missing_image() -> np.ndarray:
    """Create deterministic missing-deposit substrate image with fiducials outside ROIs."""
    img = np.full((IMAGE_HEIGHT, IMAGE_WIDTH, 3), 245, dtype=np.uint8)
    fiducials = [(20, 20), (380, 20), (20, 180), (380, 180), (200, 20), (200, 180)]
    for p in fiducials:
        cv2.circle(img, p, 5, (60, 60, 60), -1)
    return img


def generate_robustness_dataset(
    output_dir: Path,
    overwrite: bool = False,
) -> Path:
    """Generate the 14-case inspection robustness dataset and write manifest.json into output_dir.

    Preflights all target file paths and refuses to overwrite existing files unless
    overwrite=True is specified.

    Returns the path to the written manifest JSON file.
    """
    manifest_path = output_dir / "manifest.json"
    images_dir = output_dir / "images"

    case_definitions: list[dict[str, Any]] = [
        {
            "case_id": "case_01_control_clean",
            "filename": "case_01_control_clean.png",
            "description": "Clean two-site baseline control with high-contrast circular deposits.",
            "profile": DEFAULT_PROFILE,
            "expected_statuses": {
                "roi_1": RoiInspectionStatus.DETECTED,
                "roi_2": RoiInspectionStatus.DETECTED,
            },
            "provenance": {
                "basis": "construction_ground_truth",
                "annotator": "fixture_generator",
                "notes": "Crisp circular synthetic deposits at nominal centers (100, 100) and (300, 100).",
            },
            "notes": "Clean baseline control. Ground truth DETECTED on both sites.",
            "generator": lambda: _create_base_clean_image(),
        },
        {
            "case_id": "case_02_blur_mild",
            "filename": "case_02_blur_mild.png",
            "description": "Mild optical defocus: Gaussian blur kernel (5x5, sigma=1.5).",
            "profile": DEFAULT_PROFILE,
            "expected_statuses": None,
            "provenance": None,
            "notes": "Mild optical defocus: Gaussian blur (5x5, sigma=1.5). Degraded acquisition; ground truth unassigned.",
            "generator": lambda: cv2.GaussianBlur(_create_base_clean_image(), (5, 5), 1.5),
        },
        {
            "case_id": "case_03_blur_heavy",
            "filename": "case_03_blur_heavy.png",
            "description": "Severe optical defocus: Gaussian blur kernel (19x19, sigma=5.0).",
            "profile": DEFAULT_PROFILE,
            "expected_statuses": None,
            "provenance": None,
            "notes": "Severe optical defocus: Gaussian blur (19x19, sigma=5.0). Degraded acquisition; ground truth unassigned.",
            "generator": lambda: cv2.GaussianBlur(_create_base_clean_image(), (19, 19), 5.0),
        },
        {
            "case_id": "case_04_brightness_dark",
            "filename": "case_04_brightness_dark.png",
            "description": "Underexposure: global luminance scaled by 0.40.",
            "profile": DEFAULT_PROFILE,
            "expected_statuses": None,
            "provenance": None,
            "notes": "Underexposure: luminance scale 0.40 (substrate ~98, deposit ~12). Degraded acquisition; ground truth unassigned.",
            "generator": lambda: np.clip(_create_base_clean_image() * 0.4, 0, 255).astype(np.uint8),
        },
        {
            "case_id": "case_05_brightness_bright",
            "filename": "case_05_brightness_bright.png",
            "description": "Overexposure: washed-out substrate and elevated deposit floor.",
            "profile": DEFAULT_PROFILE,
            "expected_statuses": None,
            "provenance": None,
            "notes": "Overexposure: transformation img * 0.6 + 102 (substrate ~249, deposit ~120). Degraded acquisition; ground truth unassigned.",
            "generator": lambda: np.clip(_create_base_clean_image() * 0.6 + 102, 0, 255).astype(np.uint8),
        },
        {
            "case_id": "case_06_contrast_low",
            "filename": "case_06_contrast_low.png",
            "description": "Low contrast: substrate 140, deposit 125 (contrast delta 15 gray levels).",
            "profile": DEFAULT_PROFILE,
            "expected_statuses": None,
            "provenance": None,
            "notes": "Low contrast: substrate 140, deposit 125 (delta 15 gray levels). Degraded acquisition; ground truth unassigned.",
            "generator": lambda: _make_low_contrast_image(),
        },
        {
            "case_id": "case_07_glare_bounded",
            "filename": "case_07_glare_bounded.png",
            "description": "Bounded specular glare spot (radius 25 px, saturated 255) covering roi_1.",
            "profile": DEFAULT_PROFILE,
            "expected_statuses": None,
            "provenance": None,
            "notes": "Bounded specular glare: saturated circle (radius 25 px, 255) centered at (100, 100) over roi_1. roi_2 unaffected. Degraded acquisition; ground truth unassigned.",
            "generator": lambda: _make_bounded_glare_image(),
        },
        {
            "case_id": "case_08_reliable_beside_degraded",
            "filename": "case_08_reliable_beside_degraded.png",
            "description": "Mixed acquisition: crisp baseline site 1 beside severely blurred site 2.",
            "profile": DEFAULT_PROFILE,
            "expected_statuses": None,
            "provenance": None,
            "notes": "Mixed acquisition: roi_1 is clean baseline; roi_2 has severe localized Gaussian blur (17x17, sigma=4.5). Degraded acquisition; ground truth unassigned.",
            "generator": lambda: _make_reliable_beside_degraded_image(),
        },
        {
            "case_id": "case_09_clipping_edge",
            "filename": "case_09_clipping_edge.png",
            "description": "Edge clipping: sensor offset dx = +85 px, clipping deposit 1 at left image boundary.",
            "profile": CLIPPED_PROFILE,
            "expected_statuses": None,
            "provenance": None,
            "notes": "Sensor offset dx = +85 px. Deposit 1 shifted to x=15 px and clipped by 5 px at left edge x=0. ROIs transformed: roi_1_clipped [0.0, 0.20, 0.1875, 0.60] and roi_2_shifted [0.3875, 0.20, 0.30, 0.60]. Degraded acquisition; ground truth unassigned.",
            "generator": lambda: _make_clipped_edge_image(),
        },
        {
            "case_id": "case_10_missing_control",
            "filename": "case_10_missing_control.png",
            "description": "Clean baseline control for confirmed missing deposits with established substrate context.",
            "profile": DEFAULT_PROFILE,
            "expected_statuses": {
                "roi_1": RoiInspectionStatus.MISSING,
                "roi_2": RoiInspectionStatus.MISSING,
            },
            "provenance": {
                "basis": "construction_ground_truth",
                "annotator": "fixture_generator",
                "notes": "Substrate background context established by 6 perimeter fiducials; ROIs contain no deposits.",
            },
            "notes": "Clean baseline control for confirmed missing deposits with substrate context. Ground truth MISSING on both sites.",
            "generator": lambda: _create_base_missing_image(),
        },
        {
            "case_id": "case_11_uniform_unassessed_control",
            "filename": "case_11_uniform_unassessed_control.png",
            "description": "Clean baseline control for uniform unassessed input without background context.",
            "profile": DEFAULT_PROFILE,
            "expected_statuses": {
                "roi_1": RoiInspectionStatus.UNASSESSED,
                "roi_2": RoiInspectionStatus.UNASSESSED,
            },
            "provenance": {
                "basis": "construction_ground_truth",
                "annotator": "fixture_generator",
                "notes": "Flat uniform gray image (128) without fiducials or edge basis.",
            },
            "notes": "Clean baseline control for uniform unassessed input without background context. Ground truth UNASSESSED on both sites.",
            "generator": lambda: np.full((IMAGE_HEIGHT, IMAGE_WIDTH, 3), 128, dtype=np.uint8),
        },
        {
            "case_id": "case_12_glare_severe_washout",
            "filename": "case_12_glare_severe_washout.png",
            "description": "Severe camera blooming with large specular wash (saturated 255) masking right half of board.",
            "profile": DEFAULT_PROFILE,
            "expected_statuses": None,
            "provenance": None,
            "notes": "Severe camera blooming: large saturated ellipse (rx=120, ry=80, 255) covering roi_2 at (300, 100). Degraded acquisition; ground truth unassigned.",
            "generator": lambda: _make_severe_washout_image(),
        },
        {
            "case_id": "case_13_glare_on_missing",
            "filename": "case_13_glare_on_missing.png",
            "description": "Missing deposit substrate with localized glare artifact on roi_1.",
            "profile": DEFAULT_PROFILE,
            "expected_statuses": None,
            "provenance": None,
            "notes": "Substrate with fiducials, empty sites, and localized glare spot (radius 18 px, 255) on roi_1. Degraded acquisition; ground truth unassigned.",
            "generator": lambda: _make_glare_on_missing_image(),
        },
        {
            "case_id": "case_14_blur_on_missing",
            "filename": "case_14_blur_on_missing.png",
            "description": "Missing deposit substrate with severe optical blur (21x21, sigma=6.0) across fiducials.",
            "profile": DEFAULT_PROFILE,
            "expected_statuses": None,
            "provenance": None,
            "notes": "Missing-deposit substrate blurred with Gaussian filter (21x21, sigma=6.0), degrading fiducial sharpness. Degraded acquisition; ground truth unassigned.",
            "generator": lambda: cv2.GaussianBlur(_create_base_missing_image(), (21, 21), 6.0),
        },
    ]

    # Preflight collision checks before any filesystem mutations
    target_files = [manifest_path] + [images_dir / d["filename"] for d in case_definitions]
    if not overwrite:
        existing = [p for p in target_files if p.exists()]
        if existing:
            raise FileExistsError(
                f"Target file already exists: '{existing[0].name}'. "
                f"Use --overwrite to authorize replacing existing files."
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    manifest_cases: list[ManifestCase] = []

    for defn in case_definitions:
        img_data = defn["generator"]()
        img_bytes = encode_image(img_data, fmt=".png")
        img_path = images_dir / defn["filename"]
        img_path.write_bytes(img_bytes)

        rel_path = f"images/{defn['filename']}"
        m_case = ManifestCase(
            case_id=defn["case_id"],
            description=defn["description"],
            current_image_path=rel_path,
            profile=defn["profile"],
            expected_statuses=defn["expected_statuses"],
            label_provenance=defn["provenance"],
            notes=defn["notes"],
        )
        manifest_cases.append(m_case)

    manifest = DatasetManifest(
        manifest_version="v1",
        dataset_id="synthetic_inspection_robustness_v1",
        origin=DatasetOrigin.SYNTHETIC,
        description="Deterministic 14-case synthetic capture-degradation matrix evaluating blur, lighting, glare, clipping, and mixed conditions.",
        created_at="2026-10-01T00:00:00Z",
        label_provenance="Deterministic construction-grounded labels provided strictly for clean baseline controls (cases 01, 10, 11). All degraded and ambiguous cases remain unassigned.",
        cases=manifest_cases,
    )

    manifest_json = manifest.model_dump_json(indent=2)
    manifest_path.write_text(manifest_json + "\n", encoding="utf-8")
    return manifest_path


def _make_low_contrast_image() -> np.ndarray:
    """Create low-contrast image: substrate 140, deposit 125."""
    img = np.full((IMAGE_HEIGHT, IMAGE_WIDTH, 3), 140, dtype=np.uint8)
    cv2.circle(img, (100, 100), 20, (125, 125, 125), -1)
    cv2.circle(img, (300, 100), 20, (125, 125, 125), -1)
    return img


def _make_bounded_glare_image() -> np.ndarray:
    """Create image with localized specular glare spot over roi_1."""
    img = _create_base_clean_image()
    cv2.circle(img, (100, 100), 25, (255, 255, 255), -1)
    return img


def _make_reliable_beside_degraded_image() -> np.ndarray:
    """Create image with clean site 1 beside heavily blurred site 2."""
    img = _create_base_clean_image()
    img[:, 200:400] = cv2.GaussianBlur(img[:, 200:400], (17, 17), 4.5)
    return img


def _make_clipped_edge_image() -> np.ndarray:
    """Create clipped image by shifting sensor window by +85 px."""
    wide = np.full((IMAGE_HEIGHT, 485, 3), 245, dtype=np.uint8)
    cv2.circle(wide, (100, 100), 20, (30, 30, 30), -1)
    cv2.circle(wide, (300, 100), 20, (30, 30, 30), -1)
    return wide[:, 85:485].copy()


def _make_severe_washout_image() -> np.ndarray:
    """Create image with severe camera blooming over roi_2."""
    img = _create_base_clean_image()
    cv2.ellipse(img, (300, 100), (120, 80), 0, 0, 360, (255, 255, 255), -1)
    return img


def _make_glare_on_missing_image() -> np.ndarray:
    """Create missing substrate image with glare over roi_1."""
    img = _create_base_missing_image()
    cv2.circle(img, (100, 100), 18, (255, 255, 255), -1)
    return img


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for the robustness dataset generator."""
    parser = argparse.ArgumentParser(
        prog="generate_inspection_robustness",
        description="Generates deterministic synthetic inspection robustness fixtures and manifest v1.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help="Target directory where generated images and manifest.json will be saved.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Authorize overwriting existing files in the output directory.",
    )
    return parser


def main() -> int:
    """CLI entry point for the dataset generator."""
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        manifest_path = generate_robustness_dataset(
            output_dir=args.output_dir.resolve(),
            overwrite=args.overwrite,
        )
    except FileExistsError as exc:
        sys.stderr.write(f"Error generating robustness dataset: {exc}\n")
        return 1
    except (OSError, RuntimeError) as exc:
        sys.stderr.write(f"Filesystem error during generation: {exc}\n")
        return 1

    sys.stdout.write(
        f"Successfully generated inspection robustness dataset:\n"
        f"  Directory: {args.output_dir.resolve()}\n"
        f"  Manifest:  {manifest_path}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
