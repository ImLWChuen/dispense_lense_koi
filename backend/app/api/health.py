from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Reports that the web service process is responsive.",
)
def get_health() -> HealthResponse:
    """Return the health status of the service process."""
    return HealthResponse(
        status="ok",
        service="dispense-lens-api",
        version="0.1.0",
    )
