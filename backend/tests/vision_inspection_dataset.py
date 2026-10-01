"""
Dispense Lens - Local Image Dataset Evaluation Runner

Provides an offline, deterministic CLI and evaluator for team-supplied image datasets
against the existing region-inspection pipeline without requiring a running web server,
network requests, database sessions, or LLMs.

Supports versioned Manifest v1 schemas, honest labeled/unlabeled/error accounting,
path containment validation, and strict JSON report generation.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

# Ensure backend root is on sys.path for direct module execution
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import cv2
import pydantic
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.api.images import MAX_FILE_SIZE_BYTES, _sync_analyze_image
from app.schemas.image import (
    AnalysisProfile,
    ImageAnalysisMode,
    RoiInspectionStatus,
)

logger = logging.getLogger(__name__)


class DatasetOrigin(str, Enum):
    """Origin classification for dataset images."""
    SYNTHETIC = "synthetic"
    REAL = "real"


class ManifestCase(BaseModel):
    """Specification of an individual evaluation case within a dataset manifest."""
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(..., min_length=1, description="Unique identifier for the case within the manifest.")
    description: str | None = Field(default=None, description="Optional human-readable description.")
    current_image_path: str = Field(..., min_length=1, description="Relative path to the current inspection image.")
    reference_image_path: str | None = Field(default=None, description="Optional relative path to reference image.")
    profile: AnalysisProfile = Field(..., description="Analysis profile containing ROIs and limits.")
    expected_statuses: dict[str, RoiInspectionStatus] | None = Field(
        default=None,
        description="Optional ground-truth expected inspection status per ROI ID. Unmentioned ROIs are unlabeled.",
    )
    label_provenance: dict[str, Any] | str | None = Field(
        default=None,
        description="Optional metadata regarding label provenance, annotator identity, or review notes.",
    )
    notes: str | None = Field(default=None, description="Optional notes on lighting, scale, or inspection intent.")

    @field_validator("current_image_path")
    @classmethod
    def validate_current_path_relative(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("current_image_path cannot be empty.")
        if Path(s).is_absolute() or s.startswith("/") or s.startswith("\\") or (len(s) > 1 and s[1] == ":"):
            raise ValueError(f"current_image_path must be a relative path: {v}")
        return s

    @field_validator("reference_image_path")
    @classmethod
    def validate_reference_path_relative(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            return None
        if Path(s).is_absolute() or s.startswith("/") or s.startswith("\\") or (len(s) > 1 and s[1] == ":"):
            raise ValueError(f"reference_image_path must be a relative path: {v}")
        return s

    @model_validator(mode="after")
    def validate_case_integrity(self) -> ManifestCase:
        # 1. Enforce REFERENCE_IMAGE mode requires reference_image_path
        if self.profile.mode == ImageAnalysisMode.REFERENCE_IMAGE:
            if not self.reference_image_path:
                raise ValueError(
                    f"Case '{self.case_id}' uses REFERENCE_IMAGE mode but provides no reference_image_path."
                )

        # 2. Enforce expected_statuses keys must belong to profile.rois
        if self.expected_statuses:
            valid_roi_ids = {r.roi_id for r in self.profile.rois}
            for roi_id in self.expected_statuses:
                if roi_id not in valid_roi_ids:
                    raise ValueError(
                        f"Case '{self.case_id}' specifies expected status for unknown ROI ID '{roi_id}'. "
                        f"Configured ROI IDs: {sorted(valid_roi_ids)}"
                    )

        return self


class DatasetManifest(BaseModel):
    """Manifest specification v1 for local image dataset evaluation."""
    model_config = ConfigDict(extra="forbid")

    manifest_version: Literal["v1", "1.0"] = Field(
        default="v1",
        description="Manifest schema version.",
    )
    dataset_id: str = Field(..., min_length=1, description="Identifier for the dataset.")
    origin: DatasetOrigin = Field(
        ...,
        description="Dataset origin: 'synthetic' or 'real'. Do not mix origins in a single manifest.",
    )
    description: str | None = Field(default=None, description="High-level description of dataset.")
    created_at: str | None = Field(default=None, description="ISO timestamp of dataset creation.")
    label_provenance: dict[str, Any] | str | None = Field(
        default=None,
        description="Optional dataset-level provenance and reviewer notes.",
    )
    cases: list[ManifestCase] = Field(..., min_length=1, description="List of evaluation cases.")

    @model_validator(mode="after")
    def validate_unique_case_ids(self) -> DatasetManifest:
        seen: set[str] = set()
        duplicates: list[str] = []
        for case in self.cases:
            if case.case_id in seen:
                duplicates.append(case.case_id)
            seen.add(case.case_id)
        if duplicates:
            raise ValueError(f"Duplicate case_id values detected in manifest: {sorted(set(duplicates))}")
        return self


class PathValidationError(ValueError):
    """Raised when an image path fails containment or access verification."""
    pass


def resolve_and_validate_path(rel_path: str, dataset_root: Path) -> Path:
    """Resolve a relative path against dataset root and enforce strict containment and size checks.

    Prevents path traversal, absolute path escape, missing files, directory targets,
    and oversized payloads. Never leaks private absolute paths into exception messages.
    """
    clean_rel = rel_path.strip()
    if not clean_rel:
        raise PathValidationError("Path cannot be empty.")

    p = Path(clean_rel)
    if p.is_absolute() or clean_rel.startswith("/") or clean_rel.startswith("\\") or (len(clean_rel) > 1 and clean_rel[1] == ":"):
        raise PathValidationError(f"Path must be relative to dataset root: '{clean_rel}'")

    root_resolved = dataset_root.resolve()
    target_resolved = (dataset_root / p).resolve()

    # Enforce path containment within dataset root
    try:
        target_resolved.relative_to(root_resolved)
    except ValueError:
        raise PathValidationError(f"Path traversal escape detected: '{clean_rel}'")

    if not target_resolved.exists():
        raise PathValidationError(f"Image file does not exist: '{clean_rel}'")

    if not target_resolved.is_file():
        raise PathValidationError(f"Path is not a regular file: '{clean_rel}'")

    file_size = target_resolved.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        raise PathValidationError(
            f"Image file '{clean_rel}' size ({file_size} bytes) exceeds maximum limit ({MAX_FILE_SIZE_BYTES} bytes)."
        )

    return target_resolved


def get_git_commit() -> str | None:
    """Attempt to retrieve current HEAD commit hash without raising on failure."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_BACKEND_DIR,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return None


def compute_dataset_metrics(
    per_case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute aggregate dataset evaluation metrics with transparent, un-inflated denominators.

    Status accuracy denominator includes all labeled sites, even those in failed cases
    or with missing pipeline output. Dropping failures never inflates accuracy.
    Zero eligible labels yields null accuracy (None), never 0% or 100%.
    Abstention rate is computed among emitted predictions.
    False-missing rate is computed over known non-MISSING ground-truth labels.
    """
    total_cases = len(per_case_results)
    successful_cases = sum(1 for c in per_case_results if c.get("status") == "SUCCESS")
    failed_cases = sum(1 for c in per_case_results if c.get("status") == "ERROR")

    all_sites: list[dict[str, Any]] = []
    for c in per_case_results:
        all_sites.extend(c.get("sites", []))

    total_sites = len(all_sites)
    unlabeled_sites = [s for s in all_sites if not s.get("is_labeled", False)]
    labeled_sites = [s for s in all_sites if s.get("is_labeled", False)]

    unlabeled_count = len(unlabeled_sites)
    eligible_labeled_count = len(labeled_sites)

    # Sites from failed cases
    failed_case_sites = [s for s in all_sites if s.get("case_failed", False)]
    failed_case_sites_count = len(failed_case_sites)
    failed_case_labeled_sites_count = sum(1 for s in labeled_sites if s.get("case_failed", False))

    # Sites with missing output from successful cases
    missing_output_sites = [
        s for s in all_sites if not s.get("case_failed", False) and not s.get("output_present", False)
    ]
    missing_output_sites_count = len(missing_output_sites)
    missing_output_labeled_sites_count = sum(
        1 for s in labeled_sites if not s.get("case_failed", False) and not s.get("output_present", False)
    )

    # Emitted site predictions (successful case and output present)
    emitted_predictions = [
        s for s in all_sites if not s.get("case_failed", False) and s.get("output_present", False)
    ]
    emitted_predictions_count = len(emitted_predictions)
    emitted_unassessed_count = sum(
        1 for s in emitted_predictions if s.get("predicted_status") == "UNASSESSED"
    )

    # Correct / incorrect labeled status predictions
    correct_labeled_count = sum(1 for s in labeled_sites if s.get("status_match") is True)
    incorrect_labeled_count = eligible_labeled_count - correct_labeled_count

    # 1. Status Accuracy: Eligible labeled count is the honest denominator
    if eligible_labeled_count > 0:
        status_accuracy: dict[str, Any] | None = {
            "numerator": correct_labeled_count,
            "denominator": eligible_labeled_count,
            "rate": round(correct_labeled_count / eligible_labeled_count, 4),
        }
    else:
        status_accuracy = None  # Null accuracy when no labels provided

    # 2. Abstention rate among emitted predictions
    if emitted_predictions_count > 0:
        abstention_rate: dict[str, Any] = {
            "numerator": emitted_unassessed_count,
            "denominator": emitted_predictions_count,
            "rate": round(emitted_unassessed_count / emitted_predictions_count, 4),
        }
    else:
        abstention_rate = {
            "numerator": 0,
            "denominator": 0,
            "rate": 0.0,
        }

    # 3. False-missing rate over known non-MISSING labels
    known_non_missing_labels = [
        s for s in labeled_sites if s.get("expected_status") in ("DETECTED", "UNASSESSED")
    ]
    false_missing_count = sum(
        1 for s in known_non_missing_labels if s.get("predicted_status") == "MISSING"
    )
    non_missing_denom = len(known_non_missing_labels)
    if non_missing_denom > 0:
        false_missing_rate: dict[str, Any] = {
            "numerator": false_missing_count,
            "denominator": non_missing_denom,
            "rate": round(false_missing_count / non_missing_denom, 4),
        }
    else:
        false_missing_rate = {
            "numerator": 0,
            "denominator": 0,
            "rate": 0.0,
        }

    # 4. 3x3 Confusion matrix across emitted predictions for labeled sites
    valid_statuses = ["DETECTED", "MISSING", "UNASSESSED"]
    matrix: dict[str, dict[str, int]] = {exp: {pred: 0 for pred in valid_statuses} for exp in valid_statuses}
    for s in labeled_sites:
        if s.get("output_present", False) and not s.get("case_failed", False):
            exp = s.get("expected_status")
            pred = s.get("predicted_status")
            if exp in matrix and pred in matrix[exp]:
                matrix[exp][pred] += 1

    return {
        "case_counts": {
            "total_cases": total_cases,
            "successful_cases": successful_cases,
            "failed_cases": failed_cases,
        },
        "site_counts": {
            "total_sites": total_sites,
            "eligible_labeled_sites": eligible_labeled_count,
            "unlabeled_sites": unlabeled_count,
            "emitted_predictions": emitted_predictions_count,
            "correct_labeled_sites": correct_labeled_count,
            "incorrect_labeled_sites": incorrect_labeled_count,
        },
        "failure_accounting": {
            "failed_cases_count": failed_cases,
            "failed_case_sites_count": failed_case_sites_count,
            "failed_case_labeled_sites_count": failed_case_labeled_sites_count,
            "missing_output_sites_count": missing_output_sites_count,
            "missing_output_labeled_sites_count": missing_output_labeled_sites_count,
            "unlabeled_sites_count": unlabeled_count,
        },
        "status_accuracy": status_accuracy,
        "abstention_rate": abstention_rate,
        "false_missing_rate": false_missing_rate,
        "confusion_matrix": matrix,
        "boundary_accuracy": {
            "status": "not_evaluated",
            "reason": "External ground-truth masks or contours are not part of manifest v1.",
        },
    }


def _to_enum_value(val: Any) -> Any:
    """Extract string value from Enum or return as-is."""
    if val is None:
        return None
    if hasattr(val, "value"):
        return val.value
    return str(val)


def evaluate_dataset(
    manifest: DatasetManifest,
    dataset_root: Path,
) -> dict[str, Any]:
    """Execute offline evaluation of a dataset manifest against the vision pipeline.

    Processes cases sequentially, captures per-case execution timing, handles
    errors per case to permit partial run completion, and formats strict JSON output.
    """
    start_time = time.perf_counter()
    per_case_results: list[dict[str, Any]] = []

    for case in manifest.cases:
        case_start = time.perf_counter()
        try:
            # 1. Resolve and validate image paths
            curr_path = resolve_and_validate_path(case.current_image_path, dataset_root)
            curr_bytes = curr_path.read_bytes()

            ref_bytes: bytes | None = None
            if case.reference_image_path:
                ref_path = resolve_and_validate_path(case.reference_image_path, dataset_root)
                ref_bytes = ref_path.read_bytes()

            # 2. Execute synchronous vision inspection pipeline
            resp = _sync_analyze_image(
                file_bytes=curr_bytes,
                profile=case.profile,
                reference_bytes=ref_bytes,
            )
            case_elapsed = time.perf_counter() - case_start

            meas_by_id = {m.roi_id: m for m in resp.roi_measurements}
            case_sites: list[dict[str, Any]] = []

            for roi in case.profile.rois:
                roi_id = roi.roi_id
                exp_status = (
                    _to_enum_value(case.expected_statuses[roi_id])
                    if (case.expected_statuses and roi_id in case.expected_statuses)
                    else None
                )
                is_labeled = exp_status is not None

                meas = meas_by_id.get(roi_id)
                if meas is not None:
                    output_present = True
                    pred_status = _to_enum_value(meas.inspection_status)
                    status_match = (exp_status == pred_status) if is_labeled else None
                    measurements: dict[str, Any] | None = {
                        "deposit_area_px": round(float(meas.deposit_area_px), 2),
                        "target_area_px": round(float(meas.target_area_px), 2),
                        "coverage_ratio": round(float(meas.coverage_ratio), 4),
                        "overflow_ratio": round(float(meas.overflow_ratio), 4),
                        "equivalent_diameter_px": round(float(meas.equivalent_diameter_px), 2),
                        "calibrated_diameter_mm": (
                            round(float(meas.calibrated_diameter_mm), 4)
                            if meas.calibrated_diameter_mm is not None
                            else None
                        ),
                        "circularity": round(float(meas.circularity), 4),
                        "solidity": round(float(meas.solidity), 4),
                        "convexity": round(float(meas.convexity), 4),
                        "aspect_ratio": round(float(meas.aspect_ratio), 4),
                        "hole_void_ratio": round(float(meas.hole_void_ratio), 4),
                        "bubble_count": int(meas.bubble_count),
                        "segmentation_quality": round(float(meas.segmentation_quality), 4),
                        "is_missing": bool(meas.is_missing),
                    }
                    warnings = list(meas.inspection_warnings)
                else:
                    output_present = False
                    pred_status = None
                    status_match = False if is_labeled else None
                    measurements = None
                    warnings = ["Site omitted by pipeline output."]

                case_sites.append({
                    "roi_id": roi_id,
                    "is_labeled": is_labeled,
                    "expected_status": exp_status,
                    "predicted_status": pred_status,
                    "status_match": status_match,
                    "output_present": output_present,
                    "case_failed": False,
                    "measurements": measurements,
                    "warnings": warnings,
                })

                # Profile limits dictionary
                profile_limits: dict[str, Any] = {}
                if case.profile.process_limits:
                    profile_limits["process_limits"] = {
                        k: v for k, v in case.profile.process_limits.model_dump().items() if v is not None
                    }
                if case.profile.reference_limits:
                    profile_limits["reference_limits"] = {
                        k: v for k, v in case.profile.reference_limits.model_dump().items() if v is not None
                    }

            per_case_results.append({
                "case_id": case.case_id,
                "description": case.description,
                "status": "SUCCESS",
                "error": None,
                "elapsed_seconds": round(case_elapsed, 4),
                "analysis_status": _to_enum_value(resp.status),
                "current_coverage": (
                    round(float(resp.aggregate_measurements.mean_coverage), 4)
                    if resp.aggregate_measurements.mean_coverage is not None
                    else None
                ),
                "reference_coverage": (
                    round(float(resp.reference_aggregate_measurements.mean_coverage), 4)
                    if resp.reference_aggregate_measurements and resp.reference_aggregate_measurements.mean_coverage is not None
                    else None
                ),
                "inspection_coverage_status": (
                    _to_enum_value(resp.aggregate_measurements.inspection_coverage_status)
                    if resp.aggregate_measurements.inspection_coverage_status
                    else None
                ),
                "expected_roi_count": len(case.profile.rois),
                "assessed_roi_count": resp.aggregate_measurements.assessed_roi_count,
                "profile_limits": profile_limits,
                "sites": case_sites,
                "affected_observations": [
                    {
                        "observation_type": _to_enum_value(obs.observation_type),
                        "value": _to_enum_value(obs.value),
                        "detail": obs.original_text,
                        "scope": (
                            obs.metadata.get("region_evidence_scope")
                            if isinstance(obs.metadata, dict)
                            else None
                        ),
                        "affected_roi_ids": (
                            obs.metadata.get("affected_roi_ids", [])
                            if isinstance(obs.metadata, dict)
                            else []
                        ),
                    }
                    for obs in resp.observations
                ],
                "case_warnings": resp.warnings,
            })

        except Exception as exc:
            case_elapsed = time.perf_counter() - case_start
            # Record failed case without crashing runner
            case_sites = []
            for roi in case.profile.rois:
                exp_status = (
                    _to_enum_value(case.expected_statuses[roi.roi_id])
                    if (case.expected_statuses and roi.roi_id in case.expected_statuses)
                    else None
                )
                is_labeled = exp_status is not None
                case_sites.append({
                    "roi_id": roi.roi_id,
                    "is_labeled": is_labeled,
                    "expected_status": exp_status,
                    "predicted_status": None,
                    "status_match": False if is_labeled else None,
                    "output_present": False,
                    "case_failed": True,
                    "measurements": None,
                    "warnings": [f"Case execution error: {type(exc).__name__}"],
                })

            per_case_results.append({
                "case_id": case.case_id,
                "description": case.description,
                "status": "ERROR",
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
                "elapsed_seconds": round(case_elapsed, 4),
                "analysis_status": None,
                "current_coverage": None,
                "reference_coverage": None,
                "inspection_coverage_status": None,
                "expected_roi_count": len(case.profile.rois),
                "assessed_roi_count": 0,
                "profile_limits": {},
                "sites": case_sites,
                "affected_observations": [],
                "case_warnings": [f"Execution error: {type(exc).__name__}: {str(exc)}"],
            })

    total_elapsed = time.perf_counter() - start_time
    metrics_summary = compute_dataset_metrics(per_case_results)

    report: dict[str, Any] = {
        "report_version": "v1",
        "dataset_id": manifest.dataset_id,
        "origin": manifest.origin.value,
        "description": manifest.description,
        "label_provenance": manifest.label_provenance,
        "run_provenance": {
            "source_commit": get_git_commit() or "unknown",
            "python_version": sys.version.split()[0],
            "opencv_version": cv2.__version__,
            "pydantic_version": pydantic.__version__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "total_elapsed_seconds": round(total_elapsed, 4),
        "summary": metrics_summary,
        "cases": per_case_results,
    }

    return report


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for the local dataset evaluator."""
    parser = argparse.ArgumentParser(
        prog="vision_inspection_dataset",
        description=(
            "Offline runner for evaluating local image sets against the Dispense Lens "
            "region inspection pipeline. Produces structured, versioned JSON reports "
            "with honest metric denominators and failure accounting."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0    Evaluation completed successfully and report was written (including runs with individual case errors).
  1    Fatal error: manifest syntax/validation error, path traversal escape, missing file, or output exists without --overwrite.

Examples:
  # Evaluate synthetic sample dataset:
  python backend/tests/vision_inspection_dataset.py \\
    --manifest scratch/eval_sample/manifest.json \\
    --output scratch/eval_sample/report.json

  # Authorize overwriting existing report:
  python backend/tests/vision_inspection_dataset.py \\
    -m scratch/eval_sample/manifest.json \\
    -o scratch/eval_sample/report.json \\
    --overwrite
""",
    )
    parser.add_argument(
        "-m", "--manifest",
        required=True,
        type=Path,
        help="Path to the JSON dataset manifest file.",
    )
    parser.add_argument(
        "-d", "--dataset-root",
        type=Path,
        default=None,
        help="Root directory for resolving relative image paths. Defaults to the directory containing the manifest.",
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        type=Path,
        help="Target path for writing the output JSON evaluation report.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Authorize overwriting the output report if it already exists.",
    )
    return parser


def main() -> int:
    """CLI entry point. Returns exit code 0 on success, 1 on fatal error."""
    parser = build_arg_parser()
    args = parser.parse_args()

    manifest_path: Path = args.manifest.resolve()
    if not manifest_path.exists():
        sys.stderr.write(f"Fatal error: Manifest file not found: {manifest_path}\n")
        return 1
    if not manifest_path.is_file():
        sys.stderr.write(f"Fatal error: Manifest path is not a file: {manifest_path}\n")
        return 1

    dataset_root: Path = args.dataset_root.resolve() if args.dataset_root else manifest_path.parent.resolve()
    if not dataset_root.exists() or not dataset_root.is_dir():
        sys.stderr.write(f"Fatal error: Dataset root directory not found: {dataset_root}\n")
        return 1

    output_path: Path = args.output.resolve()
    if output_path.exists() and not args.overwrite:
        sys.stderr.write(
            f"Fatal error: Output report '{output_path}' already exists. Use --overwrite to replace it.\n"
        )
        return 1

    # 1. Load and parse manifest JSON
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        sys.stderr.write(f"Fatal error: Failed to parse manifest JSON: {exc}\n")
        return 1

    # 2. Validate manifest schema
    try:
        manifest = DatasetManifest.model_validate(raw_manifest)
    except Exception as exc:
        sys.stderr.write(f"Fatal error: Manifest schema validation failed:\n{exc}\n")
        return 1

    # 3. Execute evaluation
    try:
        report = evaluate_dataset(manifest, dataset_root)
    except Exception as exc:
        sys.stderr.write(f"Fatal error during dataset evaluation: {exc}\n")
        return 1

    # 4. Serialize report strictly (forbidding NaN/Infinity)
    try:
        report_json = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
    except Exception as exc:
        sys.stderr.write(f"Fatal error: Failed to serialize report to valid JSON: {exc}\n")
        return 1

    # 5. Write report to destination
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report_json + "\n", encoding="utf-8")
    except Exception as exc:
        sys.stderr.write(f"Fatal error: Failed to write report file '{output_path}': {exc}\n")
        return 1

    # Informational summary to stdout
    summary = report["summary"]
    cases_cnt = summary["case_counts"]
    sites_cnt = summary["site_counts"]
    acc = summary["status_accuracy"]
    acc_str = f"{acc['rate']*100:.1f}% ({acc['numerator']}/{acc['denominator']})" if acc else "null (no labels)"

    sys.stdout.write(
        f"Evaluation completed for dataset '{manifest.dataset_id}' ({manifest.origin.value}):\n"
        f"  Cases: {cases_cnt['total_cases']} total ({cases_cnt['successful_cases']} success, {cases_cnt['failed_cases']} failed)\n"
        f"  Sites: {sites_cnt['total_sites']} total ({sites_cnt['eligible_labeled_sites']} labeled, {sites_cnt['unlabeled_sites']} unlabeled)\n"
        f"  Status Accuracy: {acc_str}\n"
        f"  Report written to: {output_path}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
