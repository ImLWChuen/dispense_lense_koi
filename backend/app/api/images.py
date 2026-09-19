"""
DispenseIQ — Image Analysis API Route Handler

Provides the resource-safe POST /api/v1/images/analyze endpoint.
Accepts multipart file uploads with an analysis profile, offloads CPU-bound
OpenCV processing, and returns typed, calibrated image analysis results.
"""

from __future__ import annotations

import json
import logging
from typing import Any
import anyio
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.image import (
    AnalysisProfile,
    ImageAnalysisMode,
    ImageAnalysisResponse,
    ImageDimensions,
    RoiMeasurement,
)
from app.services.vision.defect_classifier import classify_defects_from_measurements
from app.services.vision.measurement import (
    calculate_aggregate_measurements,
    calculate_roi_features,
)
from app.services.vision.preprocessing import (
    ImageValidationError,
    decode_and_validate_image,
    normalize_roi_to_pixels,
)
from app.services.vision.segmentation import segment_roi

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def _sync_analyze_image(
    file_bytes: bytes,
    profile: AnalysisProfile,
    reference_bytes: bytes | None = None,
) -> ImageAnalysisResponse:
    """Synchronous CPU-bound image processing pipeline."""
    # 1. Decode and validate current image
    img, dims = decode_and_validate_image(file_bytes)

    # 2. Process all ROIs on current image
    roi_measurements: list[RoiMeasurement] = []
    for roi in profile.rois:
        target_roi, win_roi = normalize_roi_to_pixels(roi, dims.width, dims.height)
        seg_result = segment_roi(img, target_roi, win_roi)
        feat = calculate_roi_features(
            seg_result=seg_result,
            target_roi=target_roi,
            roi_id=roi.roi_id,
            mm_per_pixel=profile.mm_per_pixel,
        )
        roi_measurements.append(feat)

    all_roi_ids = [r.roi_id for r in profile.rois]
    agg = calculate_aggregate_measurements(roi_measurements, all_roi_ids)

    # 3. If REFERENCE_IMAGE mode, decode and process reference image
    ref_measurements: list[RoiMeasurement] | None = None
    ref_agg = None

    if profile.mode == ImageAnalysisMode.REFERENCE_IMAGE:
        if not reference_bytes:
            raise ImageValidationError("Reference image data is required in REFERENCE_IMAGE mode.")
        ref_img, ref_dims = decode_and_validate_image(reference_bytes)
        ref_measurements = []
        for roi in profile.rois:
            ref_target, ref_win = normalize_roi_to_pixels(roi, ref_dims.width, ref_dims.height)
            ref_seg = segment_roi(ref_img, ref_target, ref_win)
            ref_feat = calculate_roi_features(
                seg_result=ref_seg,
                target_roi=ref_target,
                roi_id=roi.roi_id,
                mm_per_pixel=profile.mm_per_pixel,
            )
            ref_measurements.append(ref_feat)
        ref_agg = calculate_aggregate_measurements(ref_measurements, all_roi_ids)

    # 4. Classify defects
    analysis_status, observations, warnings = classify_defects_from_measurements(
        mode=profile.mode,
        roi_measurements=roi_measurements,
        aggregate=agg,
        reference_measurements=ref_measurements,
        reference_aggregate=ref_agg,
        process_limits=profile.process_limits,
        reference_limits=profile.reference_limits,
    )

    return ImageAnalysisResponse(
        status=analysis_status,
        mode=profile.mode,
        image_dimensions=dims,
        roi_measurements=roi_measurements,
        aggregate_measurements=agg,
        observations=observations,
        warnings=warnings,
    )


@router.post(
    "/analyze",
    response_model=ImageAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze dispensing image",
    description=(
        "Processes an uploaded image with caller-supplied ROIs and calibration profile. "
        "Returns resolution-independent measurements and canonical diagnostic observations."
    ),
)
async def analyze_image(
    file: UploadFile = File(..., description="JPEG or PNG image file (max 10 MB)"),
    profile: str = Form(..., description="JSON-serialized AnalysisProfile specification"),
    reference_file: UploadFile | None = File(None, description="Optional reference image for REFERENCE_IMAGE mode"),
) -> ImageAnalysisResponse:
    # 1. Parse and validate profile JSON
    try:
        profile_data = json.loads(profile)
        parsed_profile = AnalysisProfile.model_validate(profile_data)
    except (json.JSONDecodeError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid profile specification: {e}",
        )

    # 2. Enforce mode-specific requirements
    if parsed_profile.mode == ImageAnalysisMode.REFERENCE_IMAGE and reference_file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="REFERENCE_IMAGE mode requires a reference_file upload.",
        )

    # 3. Read upload content with bounded memory chunking
    file_bytes = await _read_bounded_upload(file, MAX_FILE_SIZE_BYTES, "Uploaded file")

    reference_bytes: bytes | None = None
    if reference_file is not None:
        reference_bytes = await _read_bounded_upload(
            reference_file, MAX_FILE_SIZE_BYTES, "Reference file"
        )

    # 4. Offload CPU-bound OpenCV pipeline to worker thread
    try:
        response = await anyio.to_thread.run_sync(
            _sync_analyze_image,
            file_bytes,
            parsed_profile,
            reference_bytes,
        )
        return response
    except ImageValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during image analysis pipeline")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during image analysis.",
        )


async def _read_bounded_upload(
    upload: UploadFile,
    max_bytes: int = MAX_FILE_SIZE_BYTES,
    file_label: str = "Uploaded file",
) -> bytes:
    """Read upload content in bounded chunks up to max_bytes.

    If total bytes read exceed max_bytes, abort immediately and raise HTTP 413
    without buffering the remainder in memory.
    """
    if upload.size is not None and upload.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{file_label} exceeds maximum allowed size of {max_bytes // (1024 * 1024)} MB.",
        )

    chunk_size = 64 * 1024  # 64 KB chunks
    chunks: list[bytes] = []
    total_read = 0

    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{file_label} exceeds maximum allowed size of {max_bytes // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)

    return b"".join(chunks)
