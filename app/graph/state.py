"""LangGraph investigation state definitions."""

from __future__ import annotations

import operator
import uuid
from typing import Annotated, Any, Literal, NotRequired, TypedDict

InvestigationStatus = Literal[
    "pending",
    "query_analyzed",
    "planned",
    "researching",
    "completed",
    "partial",
    "failed",
]


def _merge_unique_strings(
    left: list[str] | None,
    right: list[str] | None,
) -> list[str]:
    merged: list[str] = []
    for item in [*(left or []), *(right or [])]:
        if item not in merged:
            merged.append(item)
    return merged


class InvestigationState(TypedDict):
    """Shared state flowing through the investigation graph."""

    investigation_id: str
    user_query: str
    business_type: str | None
    location: str | None
    objective: str | None
    target_customer: str | None
    research_plan: list[str]
    latitude: float | None
    longitude: float | None
    routed_agents: list[str]
    agent_results: Annotated[list[dict[str, Any]], operator.add]
    agent_runs: Annotated[list[dict[str, Any]], operator.add]
    unavailable_dimensions: Annotated[list[str], _merge_unique_strings]
    evidence: list[dict[str, Any]]
    contradictions: list[str]
    analysis: str | None
    opportunity_score: float | None
    recommendation: str | None
    confidence: float | None
    critic_status: str | None
    critic_confidence: float | None
    critic_issues: list[str]
    required_research: list[str]
    research_iteration: int
    validation_errors: list[str]
    iteration: int
    status: InvestigationStatus
    metadata: NotRequired[dict[str, Any]]


class AgentWorkItem(TypedDict):
    """Payload sent to a parallel research worker via LangGraph Send."""

    investigation_id: str
    user_query: str
    business_type: str | None
    location: str | None
    target_customer: str | None
    latitude: float | None
    longitude: float | None
    agent_name: str


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
        latitude=None,
        longitude=None,
        routed_agents=[],
        agent_results=[],
        agent_runs=[],
        unavailable_dimensions=[],
        evidence=[],
        contradictions=[],
        analysis=None,
        opportunity_score=None,
        recommendation=None,
        confidence=None,
        critic_status=None,
        critic_confidence=None,
        critic_issues=[],
        required_research=[],
        research_iteration=0,
        validation_errors=[],
        iteration=0,
        status="pending",
        metadata={},
    )
