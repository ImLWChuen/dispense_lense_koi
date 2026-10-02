"""
Dispense Lens - Vision Defect Classifier Service

Maps calibrated resolution-independent vision measurements to canonical
diagnostic evidence observations (D01-D06).
"""

from __future__ import annotations

from typing import Any

from app.schemas.diagnosis import EvidenceSource, Observation, ObservationType, StatementType
from app.schemas.image import (
    AggregateMeasurements,
    AnalysisStatus,
    ImageAnalysisMode,
    ProcessLimits,
    ReferenceLimits,
    RoiInspectionStatus,
    RoiMeasurement,
)


def _record_observation(
    obs_by_key: dict[tuple[str, str], Observation],
    obs_type: ObservationType,
    value: str,
    roi_id: str,
    base_metadata: dict[str, Any],
) -> None:
    """Record or update a deduplicated observation preserving all affected ROI IDs.

    - First occurrence creates the observation with base metadata and affected_roi_ids = [roi_id].
    - Subsequent occurrences append roi_id to affected_roi_ids (if not already present)
      without mutating primary first-site metrics or creating duplicate observations.
    """
    key = (obs_type.value, value)
    if key not in obs_by_key:
        meta = dict(base_metadata)
        meta["affected_roi_ids"] = [roi_id]
        obs_by_key[key] = Observation(
            observation_type=obs_type,
            value=value,
            source=EvidenceSource.IMAGE,
            statement_type=StatementType.AI_INFERENCE,
            metadata=meta,
        )
    else:
        existing = obs_by_key[key]
        if existing.metadata is not None:
            affected = existing.metadata.setdefault("affected_roi_ids", [])
            if roi_id not in affected:
                affected.append(roi_id)


def _snapshot_roi_measurements(m: RoiMeasurement) -> dict[str, Any]:
    """Extract a detached scalar dictionary of the 15 allowed RoiMeasurement fields."""
    status_val = m.inspection_status.value if hasattr(m.inspection_status, "value") else str(m.inspection_status)
    return {
        "inspection_status": status_val,
        "deposit_area_px": float(m.deposit_area_px),
        "target_area_px": float(m.target_area_px),
        "coverage_ratio": float(m.coverage_ratio),
        "overflow_ratio": float(m.overflow_ratio),
        "equivalent_diameter_px": float(m.equivalent_diameter_px),
        "calibrated_diameter_mm": float(m.calibrated_diameter_mm) if m.calibrated_diameter_mm is not None else None,
        "circularity": float(m.circularity),
        "solidity": float(m.solidity),
        "convexity": float(m.convexity),
        "aspect_ratio": float(m.aspect_ratio),
        "hole_void_ratio": float(m.hole_void_ratio),
        "bubble_count": int(m.bubble_count),
        "has_bubbles": bool(m.has_bubbles),
        "segmentation_quality": float(m.segmentation_quality),
    }


def _enrich_observations_with_evidence_snapshots(
    obs_by_key: dict[tuple[str, str], Observation],
    mode: ImageAnalysisMode,
    roi_measurements: list[RoiMeasurement],
    reference_measurements: list[RoiMeasurement] | None = None,
    process_limits: ProcessLimits | None = None,
    reference_limits: ReferenceLimits | None = None,
) -> None:
    """Enrich emitted observations with per-region evidence snapshots and applied limits."""
    if not obs_by_key:
        return

    # 1. Resolve applied limits
    if mode == ImageAnalysisMode.PROCESS_LIMITS and process_limits is not None:
        applied_limits = process_limits.model_dump(exclude_none=True)
    elif mode == ImageAnalysisMode.REFERENCE_IMAGE and reference_limits is not None:
        applied_limits = reference_limits.model_dump(exclude_none=True)
    else:
        applied_limits = {}

    curr_by_id = {m.roi_id: m for m in roi_measurements}
    ref_by_id = {r.roi_id: r for r in reference_measurements} if reference_measurements else {}

    for obs in obs_by_key.values():
        if obs.metadata is None:
            obs.metadata = {}

        # 2. Scope
        obs_type_val = (
            obs.observation_type.value
            if hasattr(obs.observation_type, "value")
            else str(obs.observation_type)
        )
        is_d03_inconsistent = (
            obs_type_val == ObservationType.DEPOSIT_SIZE.value
            and obs.value == "inconsistent"
        )
        obs.metadata["region_evidence_scope"] = (
            "comparison_group" if is_d03_inconsistent else "individual_regions"
        )

        # 3. Applied limits
        obs.metadata["applied_limits"] = dict(applied_limits)

        # 4. Region evidence snapshots
        affected_roi_ids = obs.metadata.get("affected_roi_ids", [])
        evidence_list: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for roi_id in affected_roi_ids:
            if roi_id in seen_ids:
                continue
            seen_ids.add(roi_id)

            curr_m = curr_by_id.get(roi_id)
            if curr_m is None:
                continue

            curr_snap = _snapshot_roi_measurements(curr_m)
            ref_snap: dict[str, Any] | None = None
            if mode == ImageAnalysisMode.REFERENCE_IMAGE and ref_by_id:
                ref_m = ref_by_id.get(roi_id)
                if ref_m is not None:
                    ref_snap = _snapshot_roi_measurements(ref_m)

            evidence_list.append({
                "roi_id": roi_id,
                "current_measurements": curr_snap,
                "reference_measurements": ref_snap,
            })

        obs.metadata["region_evidence"] = evidence_list


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

    # 1. Collect all current ROI reliability explanations
    current_unreliable_reasons: list[str] = []
    if not roi_measurements:
        current_unreliable_reasons.append("No ROI measurements available to classify.")
    else:
        for m in roi_measurements:
            if m.inspection_status == RoiInspectionStatus.UNASSESSED:
                detail = "; ".join(m.inspection_warnings) if m.inspection_warnings else "unassessed region"
                current_unreliable_reasons.append(f"ROI '{m.roi_id}' is unassessed ({detail}).")
            elif m.segmentation_quality < 0.4:
                current_unreliable_reasons.append(
                    f"ROI '{m.roi_id}' segmentation quality ({m.segmentation_quality:.2f}) is below reliable threshold."
                )

    # Check aggregate.unassessed_roi_ids for any expected ROI without measurement data
    measured_ids = {m.roi_id for m in roi_measurements} if roi_measurements else set()
    if aggregate and aggregate.unassessed_roi_ids:
        for uid in aggregate.unassessed_roi_ids:
            if uid not in measured_ids:
                current_unreliable_reasons.append(f"ROI '{uid}' is unassessed (missing measurement data).")

    # 2. Collect all reference ROI reliability explanations (when in REFERENCE_IMAGE mode)
    reference_unreliable_reasons: list[str] = []
    if mode == ImageAnalysisMode.REFERENCE_IMAGE:
        if not reference_measurements or not reference_limits:
            reference_unreliable_reasons.append(
                "REFERENCE_IMAGE mode requires reference measurements and explicit reference limits."
            )
        else:
            for ref_m in reference_measurements:
                if ref_m.inspection_status == RoiInspectionStatus.UNASSESSED:
                    detail = "; ".join(ref_m.inspection_warnings) if ref_m.inspection_warnings else "unassessed region"
                    reference_unreliable_reasons.append(
                        f"Reference ROI '{ref_m.roi_id}' is unassessed ({detail}); downgrading analysis."
                    )
                elif ref_m.segmentation_quality < 0.4:
                    reference_unreliable_reasons.append(
                        f"Reference ROI '{ref_m.roi_id}' segmentation quality ({ref_m.segmentation_quality:.2f}) is below reliable threshold; downgrading analysis."
                    )
                elif ref_m.is_missing or ref_m.inspection_status == RoiInspectionStatus.MISSING:
                    reference_unreliable_reasons.append(
                        f"Reference ROI '{ref_m.roi_id}' is missing; downgrading analysis."
                    )

        # Check reference_aggregate.unassessed_roi_ids for any expected reference ROI without measurement data
        ref_measured_ids = {r.roi_id for r in reference_measurements} if reference_measurements else set()
        if reference_aggregate and reference_aggregate.unassessed_roi_ids:
            for uid in reference_aggregate.unassessed_roi_ids:
                if uid not in ref_measured_ids:
                    reference_unreliable_reasons.append(
                        f"Reference ROI '{uid}' is unassessed (missing measurement data); downgrading analysis."
                    )

    # 3. Deduplicate and append all collected reliability explanations into top-level warnings
    for r in current_unreliable_reasons:
        if r not in warnings:
            warnings.append(r)

    if mode == ImageAnalysisMode.REFERENCE_IMAGE:
        for r in reference_unreliable_reasons:
            if r not in warnings:
                warnings.append(r)

    # 4. Mode: FEATURES_ONLY
    # Preserved as UNCALIBRATED with no observations, carrying all top-level warnings
    if mode == ImageAnalysisMode.FEATURES_ONLY:
        msg = "FEATURES_ONLY mode selected; measurements are uncalibrated and neutral."
        if msg not in warnings:
            warnings.append(msg)
        return AnalysisStatus.UNCALIBRATED, [], warnings

    # 5. Mode: PROCESS_LIMITS
    if mode == ImageAnalysisMode.PROCESS_LIMITS:
        if current_unreliable_reasons:
            return AnalysisStatus.UNRELIABLE, [], warnings

        if not process_limits:
            warnings.append("PROCESS_LIMITS mode requires explicit process limits.")
            return AnalysisStatus.UNCALIBRATED, [], warnings

        status = AnalysisStatus.CALIBRATED
        obs_by_key: dict[tuple[str, str], Observation] = {}

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
                is_missing = (m.inspection_status == RoiInspectionStatus.MISSING) or (
                    m.coverage_ratio < process_limits.min_presence_ratio
                )
                if is_missing:
                    _record_observation(
                        obs_by_key,
                        ObservationType.DEPOSIT_PRESENCE,
                        "missing",
                        m.roi_id,
                        roi_meta,
                    )
                    continue  # Skip further size/overflow/shape checks for deposits classified as missing

            # Check D01: Undersized
            if process_limits.min_coverage_ratio is not None and m.coverage_ratio < process_limits.min_coverage_ratio:
                _record_observation(
                    obs_by_key,
                    ObservationType.DEPOSIT_SIZE,
                    "undersized",
                    m.roi_id,
                    roi_meta,
                )

            # Check D02: Oversized
            if process_limits.max_coverage_ratio is not None and m.coverage_ratio > process_limits.max_coverage_ratio:
                _record_observation(
                    obs_by_key,
                    ObservationType.DEPOSIT_SIZE,
                    "oversized",
                    m.roi_id,
                    roi_meta,
                )

            # Check D05: Overflow / Excessive spreading
            if process_limits.max_overflow_ratio is not None and m.overflow_ratio > process_limits.max_overflow_ratio:
                _record_observation(
                    obs_by_key,
                    ObservationType.SPREADING_BEHAVIOUR,
                    "excessive_spread",
                    m.roi_id,
                    roi_meta,
                )

            # Check D06: Tailing / Elongated shape
            is_tailing_limit_violated = False
            if process_limits.max_aspect_ratio is not None:
                if m.aspect_ratio > process_limits.max_aspect_ratio or (m.aspect_ratio > 0 and (1.0 / m.aspect_ratio) > process_limits.max_aspect_ratio):
                    is_tailing_limit_violated = True
            if process_limits.min_aspect_ratio is not None and m.aspect_ratio < process_limits.min_aspect_ratio:
                is_tailing_limit_violated = True

            if is_tailing_limit_violated:
                _record_observation(
                    obs_by_key,
                    ObservationType.DEPOSIT_SHAPE,
                    "tailing",
                    m.roi_id,
                    roi_meta,
                )

            # Check D06: Abnormal shape (circularity, solidity, convexity)
            is_shape_abnormal = False
            if process_limits.min_circularity is not None and m.circularity < process_limits.min_circularity:
                is_shape_abnormal = True
            if process_limits.min_solidity is not None and m.solidity < process_limits.min_solidity:
                is_shape_abnormal = True
            if process_limits.min_convexity is not None and m.convexity < process_limits.min_convexity:
                is_shape_abnormal = True

            if is_shape_abnormal:
                _record_observation(
                    obs_by_key,
                    ObservationType.DEPOSIT_SHAPE,
                    "abnormal",
                    m.roi_id,
                    roi_meta,
                )

            # Check D06: Bubbles / Voids
            has_bubble_violation = False
            if process_limits.max_bubble_count is not None and m.bubble_count > process_limits.max_bubble_count:
                has_bubble_violation = True
            if process_limits.max_void_ratio is not None and m.hole_void_ratio > process_limits.max_void_ratio:
                has_bubble_violation = True

            if has_bubble_violation:
                _record_observation(
                    obs_by_key,
                    ObservationType.BUBBLE_PRESENCE,
                    "visible_bubbles",
                    m.roi_id,
                    roi_meta,
                )

        # Check D03: Inconsistent size across multiple ROIs
        if (
            process_limits.max_size_cv is not None
            and aggregate.size_cv is not None
            and aggregate.size_cv > process_limits.max_size_cv
        ):
            d03_participant_ids = [
                m.roi_id
                for m in roi_measurements
                if m.inspection_status == RoiInspectionStatus.DETECTED and m.deposit_area_px > 0
            ]
            key = (ObservationType.DEPOSIT_SIZE.value, "inconsistent")
            if key not in obs_by_key:
                obs_by_key[key] = Observation(
                    observation_type=ObservationType.DEPOSIT_SIZE,
                    value="inconsistent",
                    source=EvidenceSource.IMAGE,
                    statement_type=StatementType.AI_INFERENCE,
                    metadata={
                        "affected_roi_ids": d03_participant_ids,
                        "size_cv": aggregate.size_cv,
                        "max_size_cv": process_limits.max_size_cv,
                        "mode": mode.value,
                        "status": status.value,
                    },
                )

        _enrich_observations_with_evidence_snapshots(
            obs_by_key=obs_by_key,
            mode=mode,
            roi_measurements=roi_measurements,
            reference_measurements=None,
            process_limits=process_limits,
            reference_limits=None,
        )
        return status, list(obs_by_key.values()), warnings

    # 6. Mode: REFERENCE_IMAGE
    if mode == ImageAnalysisMode.REFERENCE_IMAGE:
        if current_unreliable_reasons or reference_unreliable_reasons:
            return AnalysisStatus.UNRELIABLE, [], warnings

        status = AnalysisStatus.CALIBRATED
        obs_by_key: dict[tuple[str, str], Observation] = {}
        ref_by_id = {r.roi_id: r for r in reference_measurements}

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
                _record_observation(
                    obs_by_key,
                    ObservationType.DEPOSIT_SIZE,
                    "undersized",
                    curr_m.roi_id,
                    roi_meta,
                )

            if reference_limits.max_reference_ratio is not None and ratio > reference_limits.max_reference_ratio:
                _record_observation(
                    obs_by_key,
                    ObservationType.DEPOSIT_SIZE,
                    "oversized",
                    curr_m.roi_id,
                    roi_meta,
                )

            if reference_limits.min_circularity_ratio is not None and ref_m.circularity > 1e-6:
                circ_ratio = curr_m.circularity / ref_m.circularity
                if circ_ratio < reference_limits.min_circularity_ratio:
                    _record_observation(
                        obs_by_key,
                        ObservationType.DEPOSIT_SHAPE,
                        "abnormal",
                        curr_m.roi_id,
                        roi_meta,
                    )

            if reference_limits.min_solidity_ratio is not None and ref_m.solidity > 1e-6:
                sol_ratio = curr_m.solidity / ref_m.solidity
                if sol_ratio < reference_limits.min_solidity_ratio:
                    _record_observation(
                        obs_by_key,
                        ObservationType.DEPOSIT_SHAPE,
                        "abnormal",
                        curr_m.roi_id,
                        roi_meta,
                    )

        _enrich_observations_with_evidence_snapshots(
            obs_by_key=obs_by_key,
            mode=mode,
            roi_measurements=roi_measurements,
            reference_measurements=reference_measurements,
            process_limits=None,
            reference_limits=reference_limits,
        )
        return status, list(obs_by_key.values()), warnings

    return AnalysisStatus.UNCALIBRATED, [], warnings
