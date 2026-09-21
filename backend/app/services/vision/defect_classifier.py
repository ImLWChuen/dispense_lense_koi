"""
Dispense Lens - Vision Defect Classifier Service

Maps calibrated resolution-independent vision measurements to canonical
diagnostic evidence observations (D01-D06).
"""

from __future__ import annotations

from app.schemas.diagnosis import EvidenceSource, Observation, ObservationType, StatementType
from app.schemas.image import (
    AggregateMeasurements,
    AnalysisStatus,
    ImageAnalysisMode,
    ProcessLimits,
    ReferenceLimits,
    RoiMeasurement,
)


def classify_defects_from_measurements(
    mode: ImageAnalysisMode,
    roi_measurements: list[RoiMeasurement],
    aggregate: AggregateMeasurements,
    reference_measurements: list[RoiMeasurement] | None = None,
    reference_aggregate: AggregateMeasurements | None = None,
    process_limits: ProcessLimits | None = None,
    reference_limits: ReferenceLimits | None = None,
) -> tuple[AnalysisStatus, list[Observation], list[str]]:
    """Classify calibrated defect observations from vision measurements."""
    warnings: list[str] = list(aggregate.warnings)
    observations: list[Observation] = []

    # 1. Mode: FEATURES_ONLY
    if mode == ImageAnalysisMode.FEATURES_ONLY:
        warnings.append("FEATURES_ONLY mode selected; measurements are uncalibrated and neutral.")
        return AnalysisStatus.UNCALIBRATED, [], warnings

    # Quality check across current ROI measurements
    if not roi_measurements:
        warnings.append("No ROI measurements available to classify.")
        return AnalysisStatus.UNRELIABLE, [], warnings

    for m in roi_measurements:
        if m.segmentation_quality < 0.4:
            warnings.append(f"ROI '{m.roi_id}' segmentation quality ({m.segmentation_quality:.2f}) is below reliable threshold.")
            return AnalysisStatus.UNRELIABLE, [], warnings

    # 2. Mode: PROCESS_LIMITS
    if mode == ImageAnalysisMode.PROCESS_LIMITS:
        if not process_limits:
            warnings.append("PROCESS_LIMITS mode requires explicit process limits.")
            return AnalysisStatus.UNCALIBRATED, [], warnings

        status = AnalysisStatus.CALIBRATED
        seen_obs_keys: set[tuple[str, str]] = set()

        for m in roi_measurements:
            roi_meta = {
                "roi_id": m.roi_id,
                "coverage_ratio": m.coverage_ratio,
                "overflow_ratio": m.overflow_ratio,
                "deposit_area_px": m.deposit_area_px,
                "target_area_px": m.target_area_px,
                "equivalent_diameter_px": m.equivalent_diameter_px,
                "calibrated_diameter_mm": m.calibrated_diameter_mm,
                "circularity": m.circularity,
                "solidity": m.solidity,
                "convexity": m.convexity,
                "aspect_ratio": m.aspect_ratio,
                "hole_void_ratio": m.hole_void_ratio,
                "bubble_count": m.bubble_count,
                "has_bubbles": m.has_bubbles,
                "mode": mode.value,
                "status": status.value,
                "segmentation_quality": m.segmentation_quality,
            }

            # Check D04: Missing deposit (strictly gated on caller supplying min_presence_ratio)
            if process_limits.min_presence_ratio is not None:
                is_missing = m.is_missing or m.deposit_area_px <= 0 or m.coverage_ratio < process_limits.min_presence_ratio
                if is_missing:
                    key = ("deposit_presence", "missing")
                    if key not in seen_obs_keys:
                        seen_obs_keys.add(key)
                        observations.append(Observation(
                            observation_type=ObservationType.DEPOSIT_PRESENCE,
                            value="missing",
                            source=EvidenceSource.IMAGE,
                            statement_type=StatementType.AI_INFERENCE,
                            metadata=roi_meta,
                        ))
                    continue  # Skip further size/overflow/shape checks for deposits classified as missing

            # Check D01: Undersized
            if process_limits.min_coverage_ratio is not None and m.coverage_ratio < process_limits.min_coverage_ratio:
                key = ("deposit_size", "undersized")
                if key not in seen_obs_keys:
                    seen_obs_keys.add(key)
                    observations.append(Observation(
                        observation_type=ObservationType.DEPOSIT_SIZE,
                        value="undersized",
                        source=EvidenceSource.IMAGE,
                        statement_type=StatementType.AI_INFERENCE,
                        metadata=roi_meta,
                    ))

            # Check D02: Oversized
            if process_limits.max_coverage_ratio is not None and m.coverage_ratio > process_limits.max_coverage_ratio:
                key = ("deposit_size", "oversized")
                if key not in seen_obs_keys:
                    seen_obs_keys.add(key)
                    observations.append(Observation(
                        observation_type=ObservationType.DEPOSIT_SIZE,
                        value="oversized",
                        source=EvidenceSource.IMAGE,
                        statement_type=StatementType.AI_INFERENCE,
                        metadata=roi_meta,
                    ))

            # Check D05: Overflow / Excessive spreading
            if process_limits.max_overflow_ratio is not None and m.overflow_ratio > process_limits.max_overflow_ratio:
                key = ("spreading_behaviour", "excessive_spread")
                if key not in seen_obs_keys:
                    seen_obs_keys.add(key)
                    observations.append(Observation(
                        observation_type=ObservationType.SPREADING_BEHAVIOUR,
                        value="excessive_spread",
                        source=EvidenceSource.IMAGE,
                        statement_type=StatementType.AI_INFERENCE,
                        metadata=roi_meta,
                    ))

            # Check D06: Tailing / Elongated shape
            is_tailing_limit_violated = False
            if process_limits.max_aspect_ratio is not None:
                if m.aspect_ratio > process_limits.max_aspect_ratio or (m.aspect_ratio > 0 and (1.0 / m.aspect_ratio) > process_limits.max_aspect_ratio):
                    is_tailing_limit_violated = True
            if process_limits.min_aspect_ratio is not None and m.aspect_ratio < process_limits.min_aspect_ratio:
                is_tailing_limit_violated = True

            if is_tailing_limit_violated:
                key = ("deposit_shape", "tailing")
                if key not in seen_obs_keys:
                    seen_obs_keys.add(key)
                    observations.append(Observation(
                        observation_type=ObservationType.DEPOSIT_SHAPE,
                        value="tailing",
                        source=EvidenceSource.IMAGE,
                        statement_type=StatementType.AI_INFERENCE,
                        metadata=roi_meta,
                    ))

            # Check D06: Abnormal shape (circularity, solidity, convexity)
            is_shape_abnormal = False
            if process_limits.min_circularity is not None and m.circularity < process_limits.min_circularity:
                is_shape_abnormal = True
            if process_limits.min_solidity is not None and m.solidity < process_limits.min_solidity:
                is_shape_abnormal = True
            if process_limits.min_convexity is not None and m.convexity < process_limits.min_convexity:
                is_shape_abnormal = True

            if is_shape_abnormal:
                key = ("deposit_shape", "abnormal")
                if key not in seen_obs_keys:
                    seen_obs_keys.add(key)
                    observations.append(Observation(
                        observation_type=ObservationType.DEPOSIT_SHAPE,
                        value="abnormal",
                        source=EvidenceSource.IMAGE,
                        statement_type=StatementType.AI_INFERENCE,
                        metadata=roi_meta,
                    ))

            # Check D06: Bubbles / Voids
            has_bubble_violation = False
            if process_limits.max_bubble_count is not None and m.bubble_count > process_limits.max_bubble_count:
                has_bubble_violation = True
            if process_limits.max_void_ratio is not None and m.hole_void_ratio > process_limits.max_void_ratio:
                has_bubble_violation = True

            if has_bubble_violation:
                key = ("bubble_presence", "visible_bubbles")
                if key not in seen_obs_keys:
                    seen_obs_keys.add(key)
                    observations.append(Observation(
                        observation_type=ObservationType.BUBBLE_PRESENCE,
                        value="visible_bubbles",
                        source=EvidenceSource.IMAGE,
                        statement_type=StatementType.AI_INFERENCE,
                        metadata=roi_meta,
                    ))

        # Check D03: Inconsistent size across multiple ROIs
        if (
            process_limits.max_size_cv is not None
            and aggregate.size_cv is not None
            and aggregate.size_cv > process_limits.max_size_cv
        ):
            key = ("deposit_size", "inconsistent")
            if key not in seen_obs_keys:
                seen_obs_keys.add(key)
                observations.append(Observation(
                    observation_type=ObservationType.DEPOSIT_SIZE,
                    value="inconsistent",
                    source=EvidenceSource.IMAGE,
                    statement_type=StatementType.AI_INFERENCE,
                    metadata={
                        "size_cv": aggregate.size_cv,
                        "max_size_cv": process_limits.max_size_cv,
                        "mode": mode.value,
                        "status": status.value,
                    },
                ))

        return status, observations, warnings

    # 3. Mode: REFERENCE_IMAGE
    if mode == ImageAnalysisMode.REFERENCE_IMAGE:
        if not reference_measurements or not reference_limits:
            warnings.append("REFERENCE_IMAGE mode requires reference measurements and explicit reference limits.")
            return AnalysisStatus.UNRELIABLE, [], warnings

        ref_by_id = {r.roi_id: r for r in reference_measurements}
        # Check reference quality
        for ref_m in reference_measurements:
            if ref_m.segmentation_quality < 0.4 or ref_m.is_missing:
                warnings.append(f"Reference ROI '{ref_m.roi_id}' is unreliable or missing; downgrading analysis.")
                return AnalysisStatus.UNRELIABLE, [], warnings

        status = AnalysisStatus.CALIBRATED
        seen_obs_keys = set()

        for curr_m in roi_measurements:
            ref_m = ref_by_id.get(curr_m.roi_id)
            if not ref_m:
                warnings.append(f"No matching reference measurement for ROI '{curr_m.roi_id}'.")
                continue

            ref_cov = ref_m.coverage_ratio
            curr_cov = curr_m.coverage_ratio

            if ref_cov <= 1e-6:
                warnings.append(f"Reference ROI '{ref_m.roi_id}' coverage is near zero; ratio cannot be computed.")
                continue

            ratio = curr_cov / ref_cov
            roi_meta = {
                "roi_id": curr_m.roi_id,
                "current_coverage": curr_cov,
                "reference_coverage": ref_cov,
                "coverage_ratio_to_reference": ratio,
                "circularity": curr_m.circularity,
                "solidity": curr_m.solidity,
                "convexity": curr_m.convexity,
                "aspect_ratio": curr_m.aspect_ratio,
                "bubble_count": curr_m.bubble_count,
                "mode": mode.value,
                "status": status.value,
            }

            if reference_limits.min_reference_ratio is not None and ratio < reference_limits.min_reference_ratio:
                key = ("deposit_size", "undersized")
                if key not in seen_obs_keys:
                    seen_obs_keys.add(key)
                    observations.append(Observation(
                        observation_type=ObservationType.DEPOSIT_SIZE,
                        value="undersized",
                        source=EvidenceSource.IMAGE,
                        statement_type=StatementType.AI_INFERENCE,
                        metadata=roi_meta,
                    ))

            if reference_limits.max_reference_ratio is not None and ratio > reference_limits.max_reference_ratio:
                key = ("deposit_size", "oversized")
                if key not in seen_obs_keys:
                    seen_obs_keys.add(key)
                    observations.append(Observation(
                        observation_type=ObservationType.DEPOSIT_SIZE,
                        value="oversized",
                        source=EvidenceSource.IMAGE,
                        statement_type=StatementType.AI_INFERENCE,
                        metadata=roi_meta,
                    ))

            if reference_limits.min_circularity_ratio is not None and ref_m.circularity > 1e-6:
                circ_ratio = curr_m.circularity / ref_m.circularity
                if circ_ratio < reference_limits.min_circularity_ratio:
                    key = ("deposit_shape", "abnormal")
                    if key not in seen_obs_keys:
                        seen_obs_keys.add(key)
                        observations.append(Observation(
                            observation_type=ObservationType.DEPOSIT_SHAPE,
                            value="abnormal",
                            source=EvidenceSource.IMAGE,
                            statement_type=StatementType.AI_INFERENCE,
                            metadata=roi_meta,
                        ))

            if reference_limits.min_solidity_ratio is not None and ref_m.solidity > 1e-6:
                sol_ratio = curr_m.solidity / ref_m.solidity
                if sol_ratio < reference_limits.min_solidity_ratio:
                    key = ("deposit_shape", "abnormal")
                    if key not in seen_obs_keys:
                        seen_obs_keys.add(key)
                        observations.append(Observation(
                            observation_type=ObservationType.DEPOSIT_SHAPE,
                            value="abnormal",
                            source=EvidenceSource.IMAGE,
                            statement_type=StatementType.AI_INFERENCE,
                            metadata=roi_meta,
                        ))

        return status, observations, warnings

    return AnalysisStatus.UNCALIBRATED, [], warnings
