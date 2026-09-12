from fastapi import FastAPI

from app.api.router import api_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    application = FastAPI(
        title="DispenseLens API",
        version="0.1.0",
        description="DispenseLens competition prototype backend service.",
    )
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
