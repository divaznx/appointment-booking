from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/")
@router.get("/health")
async def health_check():
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.environment,
        "read_replica_configured": bool(settings.database_read_url),
        "booking_model": "single+capacity",
    }
