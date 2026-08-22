"""Health check response models."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response body for the health check endpoint."""

    status: str = Field(description="Application health status", examples=["ok"])


class ReadyResponse(BaseModel):
    """Response body for the readiness probe."""

    status: str = Field(description="Readiness status", examples=["ok"])
    database: str = Field(description="Database check", examples=["ok"])
