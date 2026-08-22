"""Health check response models."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response body for the health check endpoint."""

    status: str = Field(description="Application health status", examples=["ok"])
