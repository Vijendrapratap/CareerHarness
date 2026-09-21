"""Health check routes."""

from fastapi import APIRouter

from app.core.config import settings
from app.domain.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def get_health():
    """Returns application liveness status."""
    return HealthResponse(
        status="healthy",
        app=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
    )
