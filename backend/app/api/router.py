from fastapi import APIRouter

from app.api.actions import router as actions_router
from app.api.auth import router as auth_router
from app.api.cases import router as cases_router
from app.api.causes import router as causes_router
from app.api.defects import router as defects_router
from app.api.diagnoses import router as diagnoses_router
from app.api.health import router as health_router
from app.api.questions import router as questions_router
from app.api.images import router as images_router
from app.api.analytics import router as analytics_router
from app.api.admin import router as admin_router
from app.api.telemetry import router as telemetry_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(diagnoses_router, prefix="/diagnoses", tags=["diagnoses"])
api_router.include_router(cases_router, prefix="/cases", tags=["cases"])
api_router.include_router(actions_router, prefix="/actions", tags=["actions"])
api_router.include_router(defects_router, prefix="/defects", tags=["defects"])
api_router.include_router(causes_router, prefix="/causes", tags=["causes"])
api_router.include_router(questions_router, prefix="/questions", tags=["questions"])
api_router.include_router(images_router, prefix="/images", tags=["images"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(telemetry_router, prefix="/telemetry", tags=["telemetry"])
