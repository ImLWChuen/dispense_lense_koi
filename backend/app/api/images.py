from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.services.vision.measurement import analyze_image_observations
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/analyze",
    status_code=status.HTTP_200_OK,
    summary="Analyze uploaded image",
    description="Processes an uploaded image with OpenCV to extract diagnostic observations (size, shape, bubbles, spreading, missing).",
)
async def analyze_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File provided is not an image.",
        )

    try:
        content = await file.read()
        observations = analyze_image_observations(content)
        return observations
    except ValueError as e:
        logger.error(f"Image analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error during image analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during image analysis.",
        )
