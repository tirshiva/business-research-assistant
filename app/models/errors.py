"""Structured API error model for application responses and diagnostics."""

from __future__ import annotations

from pydantic import BaseModel, Field


class APIError(BaseModel):
    """Provider-agnostic error payload for external service failures."""

    code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable error summary")
    provider: str | None = Field(
        default=None,
        description="External provider that produced the failure",
    )
    status_code: int | None = Field(
        default=None,
        description="Upstream HTTP status code when available",
    )
    details: str | None = Field(
        default=None,
        description="Optional diagnostic detail (never include secrets)",
    )
