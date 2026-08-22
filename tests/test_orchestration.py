"""Tests for multi-agent LangGraph orchestration."""

from __future__ import annotations

from typing import Any

import pytest

from app.graph.deps import ResearchOrchestrationDeps
from app.graph.graph import build_investigation_graph
from app.graph.routing import select_executable_agents, select_unavailable_dimensions
from app.graph.state import create_initial_state
from app.llm.base import LLMProvider
from app.models.research_plan import ResearchPlan
from app.services.investigation import InvestigationService

SAMPLE_QUERY = (
    "Is Sector 62, Noida a good location for a cloud kitchen targeting office workers?"
)


class PlanLLM(LLMProvider):
    name = "plan-mock"

    def __init__(self, tasks: list[str]) -> None:
        self._tasks = tasks

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[Any],
    ) -> Any:
        del system_prompt, user_prompt
        return response_model.model_validate(
            {
                "business_type": "cloud kitchen",
                "location": "Sector 62, Noida",
                "objective": "location evaluation",
                "target_customer": "office workers",
                "research_tasks": self._tasks,
            }
        )


def test_select_executable_agents_filters_plan() -> None:
    plan = ["weather", "competition", "geography", "demographics", "documents"]
    assert select_executable_agents(plan) == [
        "weather",
        "competition",
        "geography",
    ]
    assert select_unavailable_dimensions(plan) == ["demographics", "documents"]


@pytest.mark.asyncio
async def test_dynamic_routing_runs_only_selected_agents() -> None:
    deps = ResearchOrchestrationDeps.mock()
    graph = build_investigation_graph(
        llm=PlanLLM(["weather", "competition"]),
        deps=deps,
    )
    final_state = await graph.ainvoke(create_initial_state(SAMPLE_QUERY))

    assert set(final_state["routed_agents"]) == {"weather", "competition"}
    agents_run = {item["agent"] for item in final_state["agent_runs"]}
    assert agents_run == {"weather", "competition"}
    assert deps.geography_agent.run.await_count == 0
    assert deps.weather_agent.run.await_count == 1
    assert deps.competition_agent.run.await_count == 1


@pytest.mark.asyncio
async def test_parallel_research_merges_agent_outputs() -> None:
    deps = ResearchOrchestrationDeps.mock()
    graph = build_investigation_graph(
        llm=PlanLLM(["weather", "geography", "competition"]),
        deps=deps,
    )
    final_state = await graph.ainvoke(create_initial_state(SAMPLE_QUERY))

    assert len(final_state["agent_results"]) == 3
    assert len(final_state["agent_runs"]) == 3
    assert final_state["evidence"]
    assert final_state["status"] in {"completed", "partial"}


@pytest.mark.asyncio
async def test_partial_failure_continues_other_agents() -> None:
    deps = ResearchOrchestrationDeps.mock(with_failures={"competition"})
    graph = build_investigation_graph(
        llm=PlanLLM(["weather", "competition", "geography"]),
        deps=deps,
    )
    final_state = await graph.ainvoke(create_initial_state(SAMPLE_QUERY))

    assert final_state["status"] == "partial"
    assert "competition" in final_state["unavailable_dimensions"]
    statuses = {run["agent"]: run["status"] for run in final_state["agent_runs"]}
    assert statuses["competition"] == "failed"
    assert statuses["weather"] == "completed"
    assert statuses["geography"] == "completed"
    # Successful agents still contributed evidence.
    assert final_state["evidence"]


@pytest.mark.asyncio
async def test_unsupported_tasks_marked_unavailable() -> None:
    deps = ResearchOrchestrationDeps.mock()
    graph = build_investigation_graph(
        llm=PlanLLM(["demographics", "weather", "infrastructure"]),
        deps=deps,
    )
    final_state = await graph.ainvoke(create_initial_state(SAMPLE_QUERY))

    assert final_state["routed_agents"] == ["weather"]
    assert "demographics" in final_state["unavailable_dimensions"]
    assert "infrastructure" in final_state["unavailable_dimensions"]


@pytest.mark.asyncio
async def test_agent_run_observability_fields() -> None:
    deps = ResearchOrchestrationDeps.mock()
    graph = build_investigation_graph(
        llm=PlanLLM(["geography"]),
        deps=deps,
    )
    final_state = await graph.ainvoke(create_initial_state(SAMPLE_QUERY))
    run = final_state["agent_runs"][0]

    assert run["investigation_id"] == final_state["investigation_id"]
    assert run["agent"] == "geography"
    assert run["start_time"]
    assert run["completion_time"]
    assert run["status"] == "completed"
    assert run["error"] is None
    assert run["findings_count"] >= 1
    assert "nominatim.geocode" in run["allowed_tools"]


@pytest.mark.asyncio
async def test_investigation_service_end_to_end_orchestration() -> None:
    service = InvestigationService(
        graph=build_investigation_graph(
            llm=PlanLLM(["weather", "geography", "government_data"]),
            deps=ResearchOrchestrationDeps.mock(),
        )
    )
    result = await service.run({"user_query": SAMPLE_QUERY})

    assert result.status in {"completed", "partial"}
    assert set(result.routed_agents) == {
        "weather",
        "geography",
        "government_data",
    }
    assert result.evidence
    assert result.metadata.get("evidence_collection")


def test_research_plan_model_still_validates() -> None:
    plan = ResearchPlan.model_validate(
        {
            "business_type": "cloud kitchen",
            "location": "Sector 62, Noida",
            "objective": "location evaluation",
            "research_tasks": ["weather", "competition"],
        }
    )
    assert plan.research_tasks == ["weather", "competition"]
