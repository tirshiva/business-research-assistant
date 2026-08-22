"""LangGraph investigation state definitions."""

from __future__ import annotations

import uuid
from typing import Any, Literal, NotRequired, TypedDict

InvestigationStatus = Literal[
    "pending",
    "query_analyzed",
    "planned",
    "completed",
    "failed",
]


class InvestigationState(TypedDict):
    """Shared state flowing through the investigation graph.

    Fields that later modules will populate (evidence, scoring, recommendation,
    etc.) are present from the start so the graph contract remains stable.
    """

    investigation_id: str
    user_query: str
    business_type: str | None
    location: str | None
    objective: str | None
    target_customer: str | None
    research_plan: list[str]
    evidence: list[dict[str, Any]]
    contradictions: list[str]
    analysis: str | None
    opportunity_score: float | None
    recommendation: str | None
    confidence: float | None
    validation_errors: list[str]
    iteration: int
    status: InvestigationStatus
    metadata: NotRequired[dict[str, Any]]


def create_initial_state(user_query: str) -> InvestigationState:
    """Build a valid initial :class:`InvestigationState` for graph execution."""
    return InvestigationState(
        investigation_id=str(uuid.uuid4()),
        user_query=user_query.strip(),
        business_type=None,
        location=None,
        objective=None,
        target_customer=None,
        research_plan=[],
        evidence=[],
        contradictions=[],
        analysis=None,
        opportunity_score=None,
        recommendation=None,
        confidence=None,
        validation_errors=[],
        iteration=0,
        status="pending",
        metadata={},
    )
