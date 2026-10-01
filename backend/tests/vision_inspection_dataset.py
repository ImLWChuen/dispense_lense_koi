"""
Dispense Lens - Local Image Dataset Evaluation Runner

Provides an offline, deterministic CLI and evaluator for team-supplied image datasets
against the existing region-inspection pipeline without requiring a running web server,
network requests, database sessions, or LLMs.

Supports versioned Manifest v1 schemas, honest labeled/unlabeled/error accounting,
path containment validation, input protection, and strict JSON report generation.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
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
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

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
            raise ValueError("current_image_path must be a relative path without leading drive letter or slashes.")
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
            raise ValueError("reference_image_path must be a relative path without leading drive letter or slashes.")
        return s

    @model_validator(mode="after")
    def validate_case_integrity(self) -> ManifestCase:
        # 1. Enforce REFERENCE_IMAGE mode requires reference_image_path
        if self.profile.mode == ImageAnalysisMode.REFERENCE_IMAGE:
            if not self.reference_image_path:
                raise ValueError("Case in REFERENCE_IMAGE mode requires reference_image_path.")

        # 2. Enforce expected_statuses keys must belong to profile.rois
        if self.expected_statuses:
            valid_roi_ids = {r.roi_id for r in self.profile.rois}
            for roi_id in self.expected_statuses:
                if roi_id not in valid_roi_ids:
                    raise ValueError("expected_statuses contains unknown ROI ID not present in profile.")

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
        for case in self.cases:
            if case.case_id in seen:
                raise ValueError("Duplicate case_id values detected in manifest.")
            seen.add(case.case_id)
        return self


class PathValidationError(ValueError):
    """Raised when an image path fails containment or access verification."""
    pass


_SCHEMA_ALLOWLISTED_FIELDS: set[str] = {
    # Top-level manifest fields
    "manifest_version",
    "dataset_id",
    "origin",
    "description",
    "created_at",
    "label_provenance",
    "cases",
    # Case fields
    "case_id",
    "current_image_path",
    "reference_image_path",
    "profile",
    "expected_statuses",
    "notes",
    # Profile fields
    "mode",
    "rois",
    "process_limits",
    "reference_limits",
    # ROI fields
    "roi_id",
    "x",
    "y",
    "width",
    "height",
    "scale",
    "mm_per_pixel",
    # Known limit fields
    "min_coverage_ratio",
    "max_coverage_ratio",
    "min_deposit_area_px",
    "max_deposit_area_px",
    "min_target_area_px",
    "max_target_area_px",
    "max_overflow_ratio",
    "min_diameter_mm",
    "max_diameter_mm",
    "min_diameter_px",
    "max_diameter_px",
    "max_position_offset_mm",
    "max_position_offset_px",
    "min_circularity",
    "max_circularity",
    "min_aspect_ratio",
    "max_aspect_ratio",
    "min_solidity",
    "max_solidity",
    "allow_bubbles",
    "require_deposit",
}

_FIXED_EXPLANATIONS_BY_TYPE: dict[str, str] = {
    "extra_forbidden": "Extra field is not permitted in schema.",
    "missing": "Required field is missing.",
    "string_type": "Value must be a valid string.",
    "int_type": "Value must be a valid integer.",
    "int_parsing": "Value must be a valid integer.",
    "float_type": "Value must be a valid number.",
    "float_parsing": "Value must be a valid number.",
    "bool_type": "Value must be a valid boolean.",
    "bool_parsing": "Value must be a valid boolean.",
    "enum": "Value is not a recognized enum option.",
    "literal_error": "Value does not match permitted schema literal.",
    "list_type": "Value must be an array.",
    "dict_type": "Value must be an object/dictionary.",
    "string_too_short": "Value string is shorter than required minimum length.",
    "too_short": "Collection or string must not be empty.",
    "value_error": "Field value failed schema validation rules.",
}


def format_safe_schema_error(exc: ValidationError) -> str:
    """Format Pydantic ValidationError using only allowlisted field locations and fixed messages."""
    lines: list[str] = []
    for err in exc.errors():
        # 1. Format safe location using allowlisted segments, numeric indices, or <dynamic_key>
        loc_raw = err.get("loc", ())
        if not loc_raw:
            loc_str = "root"
        else:
            parts: list[str] = []
            for item in loc_raw:
                if isinstance(item, int) or (isinstance(item, str) and item.isdigit()):
                    parts.append(f"[{item}]")
                elif isinstance(item, str) and item in _SCHEMA_ALLOWLISTED_FIELDS:
                    parts.append(item)
                else:
                    parts.append("<dynamic_key>")
            loc_str = " -> ".join(parts)

        # 2. Select fixed explanation based on error type and known rule categories
        err_type = str(err.get("type", "validation_error"))
        raw_msg = str(err.get("msg", ""))

        if "relative path" in raw_msg:
            if "current_image_path" in loc_str:
                explanation = "current_image_path must be a relative path."
            elif "reference_image_path" in loc_str:
                explanation = "reference_image_path must be a relative path."
            else:
                explanation = "Path must be a relative file path without leading drive letter or slashes."
        elif "unknown ROI ID" in raw_msg:
            explanation = "expected_statuses contains unknown ROI ID not configured in profile."
            if "expected_statuses" not in loc_str:
                loc_str = f"{loc_str} -> expected_statuses"
        elif "Duplicate case_id" in raw_msg:
            explanation = "Duplicate case_id values detected in manifest."
        elif "REFERENCE_IMAGE mode requires" in raw_msg:
            explanation = "Case in REFERENCE_IMAGE mode requires reference_image_path."
        else:
            explanation = _FIXED_EXPLANATIONS_BY_TYPE.get(
                err_type,
                "Field value failed schema validation rules."
            )

        lines.append(f"  - Field '{loc_str}': {explanation} (type: {err_type})")
    return "\n".join(lines)


def sanitize_error_message(msg: str, dataset_root: Path | None = None) -> str:
    """Sanitize error messages to prevent leaking host absolute paths and private paths.

    Handles Windows paths (forward slash or backslash, including spaces),
    UNC network paths (\\\\server\\share or //server/share), and Unix/POSIX paths (including /mnt).
    """
    if not msg:
        return msg
    clean = str(msg)
    if dataset_root:
        try:
            root_str = str(dataset_root.resolve())
            clean = clean.replace(root_str, "<dataset_root>")
        except Exception:
            pass

    # Redact UNC network paths (e.g. \\server\share\... or //server/share/...)
    clean = re.sub(r"(?:\\\\|//)[^:\(\)\'\"\,\;\r\n]+", "<redacted_path>", clean)
    # Redact Windows absolute paths with forward or back slashes, supporting spaces in filenames/directories
    clean = re.sub(r"[a-zA-Z]:[/\\][^:\(\)\'\"\,\;\r\n]+", "<redacted_path>", clean)
    # Redact Unix absolute paths (e.g. /Users/..., /mnt/..., /home/..., /tmp/..., etc.)
    clean = re.sub(r"/(?:Users|home|root|var|tmp|etc|opt|app|usr|mnt)/[^:\(\)\'\"\,\;\r\n]+", "<redacted_path>", clean)
    return clean


def resolve_and_validate_path(
    rel_path: str,
    dataset_root: Path,
    case_id: str | None = None,
    field_name: str = "image_path",
) -> Path:
    """Resolve a relative path against dataset root and enforce strict containment and size checks.

    Prevents path traversal, absolute path escape, missing files, directory targets,
    and oversized payloads. Never leaks private absolute paths into exception messages.
    """
    clean_rel = rel_path.strip()
    if not clean_rel:
        raise PathValidationError(f"{field_name} cannot be empty.")

    p = Path(clean_rel)
    if p.is_absolute() or clean_rel.startswith("/") or clean_rel.startswith("\\") or (len(clean_rel) > 1 and clean_rel[1] == ":"):
        raise PathValidationError(f"{field_name} must be a relative path.")

    try:
        root_resolved = dataset_root.resolve()
        target_resolved = (dataset_root / p).resolve()
    except (OSError, RuntimeError):
        raise PathValidationError(f"Filesystem error occurred while resolving {field_name}.")

    # Enforce path containment within dataset root
    try:
        target_resolved.relative_to(root_resolved)
    except ValueError:
        raise PathValidationError(f"Path traversal escape detected in {field_name}.")

    if not target_resolved.exists():
        raise PathValidationError(f"Image file does not exist for {field_name}.")

    if not target_resolved.is_file():
        raise PathValidationError(f"Path is not a regular file for {field_name}.")

    try:
        file_size = target_resolved.stat().st_size
    except (OSError, RuntimeError):
        raise PathValidationError(f"Filesystem access error while checking {field_name} size.")

    if file_size > MAX_FILE_SIZE_BYTES:
        raise PathValidationError(
            f"Image file size ({file_size} bytes) for {field_name} exceeds maximum limit ({MAX_FILE_SIZE_BYTES} bytes)."
        )

    return target_resolved


def validate_manifest_paths_contained(manifest: DatasetManifest, dataset_root: Path) -> None:
    """Preflight check: ensure all image paths in manifest are relative and stay within dataset_root."""
    try:
        root_resolved = dataset_root.resolve()
    except (OSError, RuntimeError):
        raise PathValidationError("Filesystem access error occurred while resolving dataset root directory.")

    for case in manifest.cases:
        # Check current image path
        curr = case.current_image_path.strip()
        curr_p = Path(curr)
        if curr_p.is_absolute() or curr.startswith("/") or curr.startswith("\\") or (len(curr) > 1 and curr[1] == ":"):
            raise PathValidationError(f"Case '{case.case_id}': current_image_path must be a relative path.")
        try:
            (dataset_root / curr_p).resolve().relative_to(root_resolved)
        except ValueError:
            raise PathValidationError(f"Case '{case.case_id}': path traversal escape detected in current_image_path.")
        except (OSError, RuntimeError):
            raise PathValidationError(f"Case '{case.case_id}': filesystem error while resolving current_image_path.")

        # Check reference image path if present
        if case.reference_image_path:
            ref = case.reference_image_path.strip()
            ref_p = Path(ref)
            if ref_p.is_absolute() or ref.startswith("/") or ref.startswith("\\") or (len(ref) > 1 and ref[1] == ":"):
                raise PathValidationError(f"Case '{case.case_id}': reference_image_path must be a relative path.")
            try:
                (dataset_root / ref_p).resolve().relative_to(root_resolved)
            except ValueError:
                raise PathValidationError(f"Case '{case.case_id}': path traversal escape detected in reference_image_path.")
            except (OSError, RuntimeError):
                raise PathValidationError(f"Case '{case.case_id}': filesystem error while resolving reference_image_path.")


def get_protected_input_paths(
    manifest: DatasetManifest,
    manifest_path: Path,
    dataset_root: Path,
) -> set[Path]:
    """Collect all resolved input file paths (manifest + all case images) that must never be overwritten."""
    protected: set[Path] = set()
    try:
        protected.add(manifest_path.resolve())
    except (OSError, RuntimeError):
        protected.add(manifest_path)

    for case in manifest.cases:
        try:
            curr = (dataset_root / case.current_image_path.strip()).resolve()
            protected.add(curr)
        except (OSError, RuntimeError):
            pass

        if case.reference_image_path:
            try:
                ref = (dataset_root / case.reference_image_path.strip()).resolve()
                protected.add(ref)
            except (OSError, RuntimeError):
                pass

    return protected


def verify_output_path_safe(
    output_path: Path,
    protected_paths: set[Path],
) -> None:
    """Ensure output report path does not collide with manifest or source images (directly or via links)."""
    try:
        output_resolved = output_path.resolve()
    except (OSError, RuntimeError):
        raise PathValidationError(f"Filesystem error occurred while resolving output path: '{output_path.name}'.")

    # 1. Direct path equality
    if output_resolved in protected_paths:
        raise PathValidationError(
            f"Output path cannot overwrite evaluation inputs (manifest or source images). "
            f"Target path matches a protected evaluation input: '{output_path.name}'"
        )

    # 2. Hardlink / symlink alias check if output file already exists
    try:
        if output_path.exists():
            for prot in protected_paths:
                try:
                    if prot.exists() and os.path.samefile(output_path, prot):
                        raise PathValidationError(
                            f"Output path resolves to protected evaluation input via filesystem alias: '{output_path.name}'"
                        )
                except (FileNotFoundError, OSError):
                    pass
    except (OSError, RuntimeError):
        pass


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


def _to_enum_value(val: Any) -> Any:
    """Extract string value from Enum or return as-is."""
    if val is None:
        return None
    if hasattr(val, "value"):
        return val.value
    return str(val)


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

    # Count cases with unreviewed provenance
    unreviewed_labeled_cases_count = sum(
        1
        for c in per_case_results
        if c.get("label_provenance_status") == "unreviewed"
    )

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
            "unreviewed_labeled_cases": unreviewed_labeled_cases_count,
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


def evaluate_dataset(
    manifest: DatasetManifest,
    dataset_root: Path,
) -> dict[str, Any]:
    """Execute offline evaluation of a dataset manifest against the vision pipeline.

    Processes cases sequentially, captures per-case execution timing, handles
    errors per case to permit partial run completion, sanitizes paths/errors,
    and formats strict JSON output.
    """
    start_time = time.perf_counter()
    per_case_results: list[dict[str, Any]] = []

    for case in manifest.cases:
        case_start = time.perf_counter()

        # Resolve provenance and status
        has_labels = bool(case.expected_statuses)
        if has_labels:
            if case.label_provenance:
                provenance: Any = case.label_provenance
                prov_status = "provided"
            elif manifest.label_provenance:
                provenance = f"Inherited from dataset: {manifest.label_provenance}"
                prov_status = "inherited"
            else:
                provenance = "UNREVIEWED_PROVENANCE: Ground-truth labels supplied without documented annotator, review protocol, or dataset provenance."
                prov_status = "unreviewed"
        else:
            provenance = None
            prov_status = "unlabeled"

        case_warnings: list[str] = []
        if prov_status == "unreviewed":
            case_warnings.append("Case contains ground-truth labels but lacks documented provenance.")

        # Serialize complete profile
        profile_dump = case.profile.model_dump()

        try:
            # 1. Resolve and validate image paths
            curr_path = resolve_and_validate_path(
                case.current_image_path, dataset_root, case_id=case.case_id, field_name="current_image_path"
            )
            curr_bytes = curr_path.read_bytes()

            ref_bytes: bytes | None = None
            if case.reference_image_path:
                ref_path = resolve_and_validate_path(
                    case.reference_image_path, dataset_root, case_id=case.case_id, field_name="reference_image_path"
                )
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

            # Explicit current inspection coverage summary
            current_inspection_cov = {
                "status": _to_enum_value(resp.aggregate_measurements.inspection_coverage_status),
                "expected_roi_count": resp.aggregate_measurements.expected_roi_count,
                "assessed_roi_count": resp.aggregate_measurements.assessed_roi_count,
                "unassessed_roi_ids": list(resp.aggregate_measurements.unassessed_roi_ids),
                "missing_roi_ids": list(resp.aggregate_measurements.missing_roi_ids),
            }

            # Explicit reference inspection coverage summary if present
            ref_inspection_cov: dict[str, Any] | None = None
            if resp.reference_aggregate_measurements:
                ref_inspection_cov = {
                    "status": _to_enum_value(resp.reference_aggregate_measurements.inspection_coverage_status),
                    "expected_roi_count": resp.reference_aggregate_measurements.expected_roi_count,
                    "assessed_roi_count": resp.reference_aggregate_measurements.assessed_roi_count,
                    "unassessed_roi_ids": list(resp.reference_aggregate_measurements.unassessed_roi_ids),
                    "missing_roi_ids": list(resp.reference_aggregate_measurements.missing_roi_ids),
                }

            combined_warnings = list(case_warnings) + list(resp.warnings)

            per_case_results.append({
                "case_id": case.case_id,
                "description": case.description,
                "current_image_path": case.current_image_path,
                "reference_image_path": case.reference_image_path,
                "profile": profile_dump,
                "label_provenance": provenance,
                "label_provenance_status": prov_status,
                "notes": case.notes,
                "status": "SUCCESS",
                "error": None,
                "elapsed_seconds": round(case_elapsed, 4),
                "analysis_status": _to_enum_value(resp.status),
                "current_coverage_ratio": (
                    round(float(resp.aggregate_measurements.mean_coverage), 4)
                    if resp.aggregate_measurements.mean_coverage is not None
                    else None
                ),
                "current_inspection_coverage": current_inspection_cov,
                "reference_coverage_ratio": (
                    round(float(resp.reference_aggregate_measurements.mean_coverage), 4)
                    if resp.reference_aggregate_measurements and resp.reference_aggregate_measurements.mean_coverage is not None
                    else None
                ),
                "reference_inspection_coverage": ref_inspection_cov,
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
                "case_warnings": combined_warnings,
            })

        except Exception as exc:
            case_elapsed = time.perf_counter() - case_start

            # Determine safe error category and sanitized public message
            exc_name = type(exc).__name__
            if isinstance(exc, PathValidationError):
                category = "PATH_VALIDATION"
                clean_msg = f"Path validation error for case '{case.case_id}': image path must be a relative file within dataset root."
            elif "ImageValidationError" in exc_name or "ImageDecodeError" in exc_name:
                category = "IMAGE_VALIDATION"
                clean_msg = f"Image validation error for case '{case.case_id}': image format unsupported, damaged, or unreadable."
            elif isinstance(exc, FileNotFoundError):
                category = "FILESYSTEM_ACCESS"
                clean_msg = f"Image file not found on disk for case '{case.case_id}'."
            elif isinstance(exc, (OSError, PermissionError)):
                category = "FILESYSTEM_ACCESS"
                clean_msg = f"Filesystem access error encountered while loading image for case '{case.case_id}'."
            else:
                category = "EXECUTION_ERROR"
                clean_msg = f"Pipeline execution error encountered while inspecting case '{case.case_id}'."

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
                    "warnings": [f"Case execution error: {category}"],
                })

            err_warnings = list(case_warnings) + [f"Execution error ({category}): {clean_msg}"]

            per_case_results.append({
                "case_id": case.case_id,
                "description": case.description,
                "current_image_path": case.current_image_path,
                "reference_image_path": case.reference_image_path,
                "profile": profile_dump,
                "label_provenance": provenance,
                "label_provenance_status": prov_status,
                "notes": case.notes,
                "status": "ERROR",
                "error": {
                    "category": category,
                    "type": exc_name,
                    "message": clean_msg,
                },
                "elapsed_seconds": round(case_elapsed, 4),
                "analysis_status": None,
                "current_coverage_ratio": None,
                "current_inspection_coverage": None,
                "reference_coverage_ratio": None,
                "reference_inspection_coverage": None,
                "sites": case_sites,
                "affected_observations": [],
                "case_warnings": err_warnings,
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
            "with honest metric denominators, input protection, and failure accounting."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0    Evaluation completed successfully and report was written (including runs with individual case errors).
  1    Fatal error: manifest syntax/validation error, path traversal escape, protected input alias collision, or report exists without --overwrite.

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


def publish_report_file(temp_path: Path, output_path: Path, overwrite: bool) -> None:
    """Atomically publish report file from temp_path to output_path.

    If overwrite is True:
        Replaces output_path atomically (via temp_path.replace).
    If overwrite is False:
        Enforces strict no-clobber behavior. If output_path exists before or during
        the move, raises FileExistsError without modifying output_path.
        Fails closed on platforms/filesystems where atomic no-clobber publication is unsupported.
    """
    if overwrite:
        temp_path.replace(output_path)
        return

    # No-overwrite branch: destination MUST NOT exist
    if output_path.exists():
        raise FileExistsError(
            f"Output report '{output_path.name}' already exists. Use --overwrite to replace it."
        )

    # Move atomically with no-replace semantics
    if sys.platform == "win32":
        # On Windows, os.rename fails atomically with FileExistsError if destination exists.
        os.rename(temp_path, output_path)
    else:
        # On POSIX: os.link creates a hardlink atomically and fails if destination exists.
        try:
            os.link(temp_path, output_path)
            temp_path.unlink()
        except FileExistsError:
            raise FileExistsError(
                f"Output report '{output_path.name}' already exists. Use --overwrite to replace it."
            )
        except (OSError, NotImplementedError) as exc:
            # Fail closed: never fall back to an overwriting primitive (e.g. shutil.move)
            raise OSError(
                "Atomic no-clobber publication unsupported or failed on host filesystem."
            ) from exc


def main() -> int:
    """CLI entry point. Returns exit code 0 on success, 1 on fatal error."""
    parser = build_arg_parser()
    args = parser.parse_args()

    # Preflight resolution of CLI arguments
    try:
        manifest_path: Path = args.manifest.resolve()
        if not manifest_path.exists():
            sys.stderr.write(f"Fatal error: Manifest file not found: '{manifest_path.name}'\n")
            return 1
        if not manifest_path.is_file():
            sys.stderr.write(f"Fatal error: Manifest path is not a regular file: '{manifest_path.name}'\n")
            return 1

        dataset_root: Path = (
            args.dataset_root.resolve() if args.dataset_root else manifest_path.parent.resolve()
        )
        if not dataset_root.exists() or not dataset_root.is_dir():
            sys.stderr.write("Fatal error: Dataset root directory not found or inaccessible\n")
            return 1

        output_path: Path = args.output.resolve()
    except (OSError, RuntimeError):
        sys.stderr.write("Fatal error: Filesystem access error occurred during CLI path preflight\n")
        return 1

    # 1. Load and parse manifest JSON
    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        sys.stderr.write(f"Fatal error: Failed to read manifest file: '{manifest_path.name}'\n")
        return 1

    try:
        raw_manifest = json.loads(manifest_text)
    except json.JSONDecodeError as exc:
        sys.stderr.write(
            f"Fatal error: Manifest syntax error: Invalid JSON at line {exc.lineno}, column {exc.colno}\n"
        )
        return 1

    # 2. Validate manifest schema
    try:
        manifest = DatasetManifest.model_validate(raw_manifest)
    except ValidationError as exc:
        safe_schema_msg = format_safe_schema_error(exc)
        sys.stderr.write(f"Fatal error: Manifest schema validation failed:\n{safe_schema_msg}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"Fatal error: Manifest validation failed: {type(exc).__name__}\n")
        return 1

    # 3. Preflight security: check for path traversal escapes in manifest image paths
    try:
        validate_manifest_paths_contained(manifest, dataset_root)
    except PathValidationError as exc:
        sys.stderr.write(f"Fatal error: {exc}\n")
        return 1

    # 4. Input Protection: ensure output path does not collide with manifest or source images
    protected_paths = get_protected_input_paths(manifest, manifest_path, dataset_root)
    try:
        verify_output_path_safe(output_path, protected_paths)
    except PathValidationError as exc:
        sys.stderr.write(f"Fatal error: {exc}\n")
        return 1

    # 5. Overwrite protection: refuse replacing existing report without explicit --overwrite
    if output_path.exists() and not args.overwrite:
        sys.stderr.write(
            f"Fatal error: Output report '{output_path.name}' already exists. Use --overwrite to replace it.\n"
        )
        return 1

    # 6. Execute evaluation
    try:
        report = evaluate_dataset(manifest, dataset_root)
    except Exception as exc:
        exc_name = type(exc).__name__
        sys.stderr.write(f"Fatal error during dataset evaluation: {exc_name} encountered.\n")
        return 1

    # 7. Serialize report strictly (forbidding NaN/Infinity)
    try:
        report_json = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
    except Exception as exc:
        sys.stderr.write(f"Fatal error: Failed to serialize report to valid JSON: {type(exc).__name__}\n")
        return 1

    # 8. Write report to destination atomically and enforce no-clobber publication
    temp_path = output_path.with_name(f".tmp_{output_path.name}_{uuid.uuid4().hex}")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(report_json + "\n", encoding="utf-8")
        publish_report_file(temp_path, output_path, overwrite=args.overwrite)
    except FileExistsError:
        sys.stderr.write(
            f"Fatal error: Output report '{output_path.name}' already exists. Use --overwrite to replace it.\n"
        )
        return 1
    except OSError as exc:
        if "Atomic no-clobber publication unsupported" in str(exc):
            sys.stderr.write(f"Fatal error: {exc}\n")
        else:
            sys.stderr.write(f"Fatal error: Filesystem access error while writing report file '{output_path.name}'\n")
        return 1
    except RuntimeError:
        sys.stderr.write(f"Fatal error: Filesystem access error while writing report file '{output_path.name}'\n")
        return 1
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

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
        f"  Report written to: {output_path.name}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
