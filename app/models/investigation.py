"""Request/response models for investigation graph execution."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class InvestigationRequest(BaseModel):
    """Input payload accepted by the investigation service."""

    user_query: str = Field(
        ...,
        min_length=1,
        description="Natural-language business investigation question",
        examples=[
            "Is Sector 62, Noida a good location for a cloud kitchen "
            "targeting office workers?"
        ],
    )

    @field_validator("user_query")
    @classmethod
    def normalize_user_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("user_query must not be empty or whitespace")
        return normalized


class InvestigationResult(BaseModel):
    """Validated investigation state returned to callers."""

    investigation_id: str
    user_query: str
    business_type: str | None = None
    location: str | None = None
    objective: str | None = None
    target_customer: str | None = None
    research_plan: list[str] = Field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None
    routed_agents: list[str] = Field(default_factory=list)
    agent_results: list[dict[str, Any]] = Field(default_factory=list)
    agent_runs: list[dict[str, Any]] = Field(default_factory=list)
    unavailable_dimensions: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    analysis: str | None = None
    opportunity_score: float | None = None
    recommendation: str | None = None
    confidence: float | None = None
    critic_status: str | None = None
    critic_confidence: float | None = None
    critic_issues: list[str] = Field(default_factory=list)
    required_research: list[str] = Field(default_factory=list)
    research_iteration: int = 0
    validation_errors: list[str] = Field(default_factory=list)
    iteration: int = 0
    status: Literal[
        "pending",
        "query_analyzed",
        "planned",
        "researching",
        "completed",
        "partial",
        "failed",
    ]
    metadata: dict[str, Any] = Field(default_factory=dict)
