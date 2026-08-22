"""Tests for LangGraph investigation state and execution."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.exceptions import InvestigationInputError
from app.graph.deps import ResearchOrchestrationDeps
from app.graph.graph import build_investigation_graph
from app.graph.nodes.query_analyzer import query_analyzer
from app.graph.state import InvestigationState, create_initial_state
from app.llm.local import LocalLLMProvider
from app.models.investigation import InvestigationRequest
from app.services.investigation import InvestigationService

SAMPLE_QUERY = (
    "Is Sector 62, Noida a good location for a cloud kitchen targeting office workers?"
)


def _graph():
    return build_investigation_graph(
        llm=LocalLLMProvider(),
        deps=ResearchOrchestrationDeps.mock(),
    )


def test_initial_state_defaults() -> None:
    state = create_initial_state(SAMPLE_QUERY)

    assert isinstance(state, dict)
    assert state["investigation_id"]
    assert state["user_query"] == SAMPLE_QUERY
    assert state["business_type"] is None
    assert state["location"] is None
    assert state["objective"] is None
    assert state["target_customer"] is None
    assert state["research_plan"] == []
    assert state["routed_agents"] == []
    assert state["agent_results"] == []
    assert state["evidence"] == []
    assert state["contradictions"] == []
    assert state["analysis"] is None
    assert state["opportunity_score"] is None
    assert state["recommendation"] is None
    assert state["confidence"] is None
    assert state["validation_errors"] == []
    assert state["iteration"] == 0
    assert state["status"] == "pending"


@pytest.mark.asyncio
async def test_query_analyzer_mutates_state() -> None:
    initial = create_initial_state(SAMPLE_QUERY)
    updates = await query_analyzer(initial)

    assert updates["business_type"] == "cloud_kitchen"
    assert updates["location"] == "Sector 62, Noida"
    assert updates["target_customer"] == "office workers"
    assert updates["objective"]
    assert updates["status"] == "query_analyzed"
    assert updates["iteration"] == 1
    assert updates["validation_errors"] == []
    assert "cloud kitchen" in updates["objective"].lower()


@pytest.mark.asyncio
async def test_graph_execution_start_to_end() -> None:
    graph = _graph()
    initial = create_initial_state(SAMPLE_QUERY)

    final_state: InvestigationState = await graph.ainvoke(initial)

    assert final_state["investigation_id"] == initial["investigation_id"]
    assert final_state["user_query"] == SAMPLE_QUERY
    assert final_state["business_type"] == "cloud kitchen"
    assert final_state["location"] == "Sector 62, Noida"
    assert final_state["target_customer"] == "office workers"
    assert final_state["status"] in {"completed", "partial"}
    assert "demographics" in final_state["research_plan"]
    assert "competition" in final_state["research_plan"]
    assert "geography" in final_state["research_plan"]
    assert "competition" in final_state["routed_agents"]
    assert "geography" in final_state["routed_agents"]
    assert final_state["agent_results"]
    assert final_state["evidence"]
    assert final_state["opportunity_score"] is None


@pytest.mark.asyncio
async def test_investigation_service_returns_valid_state() -> None:
    service = InvestigationService(graph=_graph())

    result = await service.run({"user_query": SAMPLE_QUERY})

    assert result.user_query == SAMPLE_QUERY
    assert result.business_type == "cloud kitchen"
    assert result.location == "Sector 62, Noida"
    assert result.status in {"completed", "partial"}
    assert result.validation_errors == [] or isinstance(result.validation_errors, list)
    assert result.research_plan
    assert result.evidence


@pytest.mark.asyncio
async def test_graph_completion_status() -> None:
    service = InvestigationService(graph=_graph())
    result = await service.run(InvestigationRequest(user_query=SAMPLE_QUERY))

    assert result.status in {"completed", "partial"}
    assert result.analysis is not None
    assert result.recommendation is None
    assert result.metadata.get("research_plan")
    assert result.agent_runs


def test_invalid_input_empty_query_model() -> None:
    with pytest.raises(ValidationError):
        InvestigationRequest(user_query="   ")


@pytest.mark.asyncio
async def test_invalid_input_service_raises() -> None:
    service = InvestigationService(graph=_graph())

    with pytest.raises(InvestigationInputError):
        await service.run({"user_query": ""})

    with pytest.raises(InvestigationInputError):
        await service.run({})


@pytest.mark.asyncio
async def test_query_analyzer_empty_query_marks_failed() -> None:
    state = create_initial_state("placeholder")
    state["user_query"] = ""

    updates = await query_analyzer(state)

    assert updates["status"] == "failed"
    assert updates["validation_errors"]
    assert updates["iteration"] == 1
