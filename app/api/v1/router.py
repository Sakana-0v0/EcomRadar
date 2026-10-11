from fastapi import APIRouter
from app.api.v1.endpoints import report, health

router = APIRouter()

router.include_router(report.router, prefix="/report", tags=["report"])
router.include_router(health.router, tags=["health"])
