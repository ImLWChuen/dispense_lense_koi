from fastapi import APIRouter

from app.api.diagnoses import router as diagnoses_router
from app.api.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(diagnoses_router, prefix="/diagnoses", tags=["diagnoses"])
