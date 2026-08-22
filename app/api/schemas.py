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
    """Start a new investigation from a question and optional form fields."""

    query: str | None = Field(
        default=None,
        description="Natural-language business question",
        examples=[
            "Is Sector 62, Noida a good location for a cloud kitchen "
            "targeting office workers?"
        ],
    )
    research_question: str | None = Field(
        default=None,
        description="Alias for query used by the web form",
    )
    business_type: str | None = None
    location: str | None = None
    target_customer: str | None = None
    budget: str | None = None

    @field_validator(
        "query",
        "research_question",
        "business_type",
        "location",
        "target_customer",
        "budget",
    )
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AgentProgress(BaseModel):
    running: list[str] = Field(default_factory=list)
    completed: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    unavailable: list[str] = Field(default_factory=list)


class InsightItem(BaseModel):
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)


class InsightsSummary(BaseModel):
    observations: list[InsightItem] = Field(default_factory=list)
    opportunities: list[InsightItem] = Field(default_factory=list)
    risks: list[InsightItem] = Field(default_factory=list)
    unknowns: list[InsightItem] = Field(default_factory=list)


class AdditionalResearchRequest(BaseModel):
    """Optional follow-up research request for an existing investigation."""

    tasks: list[str] = Field(default_factory=list)


class InvestigationCreatedResponse(BaseModel):
    id: str
    status: LifecycleStatus


class InvestigationStatusResponse(BaseModel):
    id: str
    status: LifecycleStatus
    stage: LifecycleStatus
    agents: AgentProgress = Field(default_factory=AgentProgress)
    evidence_count: int = 0
    research_iteration: int = 0
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
    stage: LifecycleStatus
    business_type: str | None = None
    location: str | None = None
    objective: str | None = None
    target_customer: str | None = None
    budget: str | None = None
    plan: list[str] = Field(default_factory=list)
    tasks: list[ResearchTaskResponse] = Field(default_factory=list)
    agents: AgentProgress = Field(default_factory=AgentProgress)
    evidence_count: int = 0
    research_iteration: int = 0
    opportunity_score: float | None = None
    recommendation: str | None = None
    confidence: float | None = None
    scores: ScoreSummary | None = None
    insights: InsightsSummary | None = None
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
    source_type: str | None = None
    retrieved_at: datetime
    timestamp: datetime
    confidence: float
    document_id: str | None = None
    page: int | None = None


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
    confidence: float | None = None
    insights: InsightsSummary | None = None
    critic: CriticSummary | None = None
    report: str
    created_at: datetime
    updated_at: datetime
