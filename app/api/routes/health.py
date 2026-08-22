"""Health and readiness endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.models.health import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Liveness probe — process is up. Does not check dependencies."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
async def ready_check(request: Request) -> ReadyResponse | JSONResponse:
    """Readiness probe — database is reachable."""
    engine = getattr(request.app.state, "db_engine", None)
    if engine is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "unknown"},
        )
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "error"},
        )
    return ReadyResponse(status="ok", database="ok")
