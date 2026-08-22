"""Public API schemas — no LangGraph investigation state."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

LifecycleStatus = Literal[
    "CREATED",
    "PLANNING",
    "RESEARCHING",
    "VALIDATING",
    "ANALYZING",
    "REVIEWING",
    "COMPLETED",
    "FAILED",
]


class ErrorResponse(BaseModel):
    """Stable client-facing error body."""

    code: str
    message: str
    details: str | None = None


class CreateInvestigationRequest(BaseModel):
    """Start a new investigation."""

    query: str = Field(
        ...,
        min_length=1,
        description="Natural-language business question",
        examples=[
            "Is Sector 62, Noida a good location for a cloud kitchen "
            "targeting office workers?"
        ],
    )

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be empty or whitespace")
        return normalized


class AdditionalResearchRequest(BaseModel):
    """Optional follow-up research request for an existing investigation."""

    tasks: list[str] = Field(default_factory=list)


class InvestigationCreatedResponse(BaseModel):
    id: str
    status: LifecycleStatus


class InvestigationStatusResponse(BaseModel):
    id: str
    status: LifecycleStatus
    created_at: datetime
    updated_at: datetime
    error: str | None = None


class ResearchTaskResponse(BaseModel):
    task_type: str
    status: str
    findings_count: int = 0
    error: str | None = None


class CriticSummary(BaseModel):
    status: str | None = None
    confidence: float | None = None
    issues: list[str] = Field(default_factory=list)
    required_research: list[str] = Field(default_factory=list)


class ScoreSummary(BaseModel):
    overall_score: float | None = None
    recommendation: str | None = None
    dimensions: list[dict[str, Any]] = Field(default_factory=list)


class InvestigationResponse(BaseModel):
    """Public investigation snapshot."""

    id: str
    query: str
    status: LifecycleStatus
    business_type: str | None = None
    location: str | None = None
    objective: str | None = None
    target_customer: str | None = None
    plan: list[str] = Field(default_factory=list)
    tasks: list[ResearchTaskResponse] = Field(default_factory=list)
    opportunity_score: float | None = None
    recommendation: str | None = None
    confidence: float | None = None
    critic: CriticSummary | None = None
    created_at: datetime
    updated_at: datetime


class EvidenceItemResponse(BaseModel):
    evidence_id: str
    agent: str
    claim: str
    value: Any = None
    claim_kind: str
    source_name: str | None = None
    source_url: str | None = None
    retrieved_at: datetime
    confidence: float


class EvidenceListResponse(BaseModel):
    investigation_id: str
    items: list[EvidenceItemResponse] = Field(default_factory=list)


class InvestigationReportResponse(BaseModel):
    investigation_id: str
    query: str
    status: LifecycleStatus
    location: str | None = None
    business_type: str | None = None
    plan: list[str] = Field(default_factory=list)
    scores: ScoreSummary | None = None
    recommendation: str | None = None
    critic: CriticSummary | None = None
    report: str
    created_at: datetime
    updated_at: datetime
