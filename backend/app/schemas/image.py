"""
DispenseIQ — Image Analysis Schemas and Contracts

Defines the typed data contracts for calibrated, resolution-independent
computer-vision operations, normalized ROIs, process/reference limits,
and structured diagnostic image analysis responses.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.diagnosis import Observation


class ImageAnalysisMode(str, Enum):
    """Analysis modes for vision evaluation."""
    FEATURES_ONLY = "FEATURES_ONLY"
    PROCESS_LIMITS = "PROCESS_LIMITS"
    REFERENCE_IMAGE = "REFERENCE_IMAGE"


class AnalysisStatus(str, Enum):
    """Calibrated status of image processing analysis."""
    CALIBRATED = "CALIBRATED"
    UNCALIBRATED = "UNCALIBRATED"
    UNRELIABLE = "UNRELIABLE"


class NormalizedROI(BaseModel):
    """Normalized rectangular region of interest with coordinates in [0.0, 1.0]."""
    model_config = ConfigDict(extra="forbid")

    roi_id: str = Field(..., min_length=1)
    x: float = Field(..., ge=0.0, le=1.0, description="Top-left X coordinate normalized to image width")
    y: float = Field(..., ge=0.0, le=1.0, description="Top-left Y coordinate normalized to image height")
    width: float = Field(..., gt=0.0, le=1.0, description="Width normalized to image width")
    height: float = Field(..., gt=0.0, le=1.0, description="Height normalized to image height")

    @field_validator("roi_id")
    @classmethod
    def validate_roi_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("roi_id must not be blank.")
        return s

    @model_validator(mode="after")
    def validate_bounds(self) -> NormalizedROI:
        if self.x + self.width > 1.0 + 1e-6:
            raise ValueError(f"ROI x + width ({self.x + self.width:.4f}) exceeds image boundary (1.0).")
        if self.y + self.height > 1.0 + 1e-6:
            raise ValueError(f"ROI y + height ({self.y + self.height:.4f}) exceeds image boundary (1.0).")
        return self


class PixelROI(BaseModel):
    """Pixel-coordinate region of interest."""
    model_config = ConfigDict(extra="forbid")

    roi_id: str
    x: int
    y: int
    width: int
    height: int


class ProcessLimits(BaseModel):
    """Explicit, caller-supplied process limits.

    No manufacturing defaults are assumed; only supplied fields are checked.
    At least one limit field must be defined.
    """
    model_config = ConfigDict(extra="forbid")

    min_coverage_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    max_coverage_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    max_overflow_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    max_size_cv: float | None = Field(default=None, ge=0.0)
    min_presence_ratio: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_limits(self) -> ProcessLimits:
        if (
            self.min_coverage_ratio is None
            and self.max_coverage_ratio is None
            and self.max_overflow_ratio is None
            and self.max_size_cv is None
            and self.min_presence_ratio is None
        ):
            raise ValueError("ProcessLimits requires at least one limit to be defined.")
        if (
            self.min_coverage_ratio is not None
            and self.max_coverage_ratio is not None
            and self.min_coverage_ratio > self.max_coverage_ratio
        ):
            raise ValueError("min_coverage_ratio cannot be greater than max_coverage_ratio.")
        return self


class ReferenceLimits(BaseModel):
    """Explicit, caller-supplied comparison tolerances against a reference image."""
    model_config = ConfigDict(extra="forbid")

    min_reference_ratio: float | None = Field(default=None, gt=0.0)
    max_reference_ratio: float | None = Field(default=None, gt=0.0)
    tolerance_ratio: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def resolve_and_validate(self) -> ReferenceLimits:
        if self.tolerance_ratio is not None:
            if self.min_reference_ratio is None:
                self.min_reference_ratio = max(0.0, 1.0 - self.tolerance_ratio)
            if self.max_reference_ratio is None:
                self.max_reference_ratio = 1.0 + self.tolerance_ratio

        if self.min_reference_ratio is not None and self.max_reference_ratio is not None:
            if self.min_reference_ratio > self.max_reference_ratio:
                raise ValueError("min_reference_ratio cannot be greater than max_reference_ratio.")

        if self.min_reference_ratio is None and self.max_reference_ratio is None:
            raise ValueError("Reference mode requires at least one of min_reference_ratio, max_reference_ratio, or tolerance_ratio.")
        return self


class AnalysisProfile(BaseModel):
    """Complete analysis specification supplied by the caller."""
    model_config = ConfigDict(extra="forbid")

    mode: ImageAnalysisMode = ImageAnalysisMode.FEATURES_ONLY
    rois: list[NormalizedROI] = Field(..., min_length=1)
    mm_per_pixel: float | None = Field(default=None, gt=0.0)
    process_limits: ProcessLimits | None = None
    reference_limits: ReferenceLimits | None = None

    @model_validator(mode="after")
    def validate_profile(self) -> AnalysisProfile:
        # 1. Enforce unique non-blank ROI IDs
        roi_ids = [r.roi_id for r in self.rois]
        if len(set(roi_ids)) != len(roi_ids):
            raise ValueError(f"Duplicate roi_id values detected: {roi_ids}")

        # 2. Enforce mode requirements and exclusivity
        if self.mode == ImageAnalysisMode.FEATURES_ONLY:
            if self.process_limits is not None:
                raise ValueError("FEATURES_ONLY mode must not include process_limits.")
            if self.reference_limits is not None:
                raise ValueError("FEATURES_ONLY mode must not include reference_limits.")

        elif self.mode == ImageAnalysisMode.PROCESS_LIMITS:
            if not self.process_limits:
                raise ValueError("PROCESS_LIMITS mode requires process_limits to be defined.")
            if self.reference_limits is not None:
                raise ValueError("PROCESS_LIMITS mode must not include reference_limits.")

        elif self.mode == ImageAnalysisMode.REFERENCE_IMAGE:
            if not self.reference_limits:
                raise ValueError("REFERENCE_IMAGE mode requires reference_limits to be defined.")
            if self.process_limits is not None:
                raise ValueError("REFERENCE_IMAGE mode must not include process_limits.")

        return self


class ImageDimensions(BaseModel):
    """Dimensions of a decoded image."""
    model_config = ConfigDict(extra="forbid")

    width: int
    height: int
    channels: int = 3


class RoiMeasurement(BaseModel):
    """Detailed geometric and optical measurements for a single ROI."""
    model_config = ConfigDict(extra="ignore")

    roi_id: str
    deposit_area_px: float
    target_area_px: float
    coverage_ratio: float
    overflow_ratio: float
    equivalent_diameter_px: float
    calibrated_diameter_mm: float | None = None
    circularity: float
    solidity: float
    aspect_ratio: float
    hole_void_ratio: float
    segmentation_quality: float
    is_missing: bool = False


class AggregateMeasurements(BaseModel):
    """Summary metrics aggregated across all ROIs."""
    model_config = ConfigDict(extra="ignore")

    mean_coverage: float | None = None
    size_cv: float | None = None
    missing_roi_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ImageAnalysisResponse(BaseModel):
    """Complete structured response from the image analysis pipeline."""
    model_config = ConfigDict(extra="ignore")

    status: AnalysisStatus
    mode: ImageAnalysisMode
    image_dimensions: ImageDimensions
    roi_measurements: list[RoiMeasurement] = Field(default_factory=list)
    aggregate_measurements: AggregateMeasurements
    observations: list[Observation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
