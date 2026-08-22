"""Shared schemas for research agent inputs and outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

AgentName = Literal["weather", "geography", "competition", "government_data"]
AgentStatus = Literal["completed", "partial", "failed", "data_unavailable"]


class AgentSource(BaseModel):
    """Provenance metadata for a finding."""

    name: str
    url: str | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tool: str | None = None
    notes: str | None = None


class AgentFinding(BaseModel):
    """A single structured finding produced by an agent."""

    title: str
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class AgentResult(BaseModel):
    """Common agent response envelope."""

    agent: AgentName
    findings: list[AgentFinding] = Field(default_factory=list)
    sources: list[AgentSource] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    status: AgentStatus
    errors: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, value: float) -> float:
        return round(float(value), 4)
