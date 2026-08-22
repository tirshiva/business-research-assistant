"""Tests for the research planner and LLM-backed planning node."""

from __future__ import annotations

from typing import Any, TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from app.core.exceptions import LLMStructuredOutputError, PlannerError
from app.graph.deps import ResearchOrchestrationDeps
from app.graph.graph import build_investigation_graph
from app.graph.state import create_initial_state
from app.llm.base import LLMProvider
from app.models.research_plan import ResearchPlan
from app.services.investigation import InvestigationService
from app.services.planner import ResearchPlanner

T = TypeVar("T", bound=BaseModel)

SAMPLE_QUERY = (
    "Is Sector 62, Noida a good location for a cloud kitchen targeting office workers?"
)


class MockLLMProvider(LLMProvider):
    """Deterministic LLM double for unit tests."""

    name = "mock"

    def __init__(
        self,
        *,
        payload: dict[str, Any] | None = None,
        payloads: list[dict[str, Any] | Exception] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._payload = payload
        self._payloads = list(payloads or [])
        self._error = error
        self.calls = 0

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        del system_prompt, user_prompt
        self.calls += 1
        if self._error is not None:
            raise self._error
        if self._payloads:
            item = self._payloads.pop(0)
            if isinstance(item, Exception):
                raise item
            payload = item
        else:
            assert self._payload is not None
            payload = self._payload
        try:
            return response_model.model_validate(payload)
        except ValidationError as exc:
            raise LLMStructuredOutputError(
                "Mock LLM returned invalid structured output",
                provider=self.name,
                details=str(exc),
            ) from exc


def _valid_plan_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "business_type": "cloud kitchen",
        "location": "Sector 62, Noida",
        "objective": "location evaluation",
        "target_customer": "office workers",
        "research_tasks": [
            "demographics",
            "competition",
            "geography",
            "infrastructure",
            "weather",
        ],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_valid_plan_from_mocked_llm() -> None:
    llm = MockLLMProvider(payload=_valid_plan_payload())
    planner = ResearchPlanner(llm, max_retries=0, retry_backoff_seconds=0)

    plan = await planner.create_plan(user_query=SAMPLE_QUERY)

    assert isinstance(plan, ResearchPlan)
    assert plan.business_type == "cloud kitchen"
    assert plan.location == "Sector 62, Noida"
    assert plan.objective == "location evaluation"
    assert plan.target_customer == "office workers"
    assert plan.research_tasks == [
        "demographics",
        "competition",
        "geography",
        "infrastructure",
        "weather",
    ]
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_malformed_llm_response_retries_then_fails() -> None:
    llm = MockLLMProvider(
        payloads=[
            {"not": "a plan"},
            {
                "business_type": "x",
                "location": "y",
                "objective": "z",
                "research_tasks": [],
            },
        ]
    )
    planner = ResearchPlanner(llm, max_retries=1, retry_backoff_seconds=0)

    with pytest.raises(PlannerError) as exc_info:
        await planner.create_plan(user_query=SAMPLE_QUERY)

    assert exc_info.value.attempts == 2
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_unsupported_task_is_rejected() -> None:
    llm = MockLLMProvider(
        payload=_valid_plan_payload(research_tasks=["demographics", "telepathy"])
    )
    planner = ResearchPlanner(llm, max_retries=0, retry_backoff_seconds=0)

    with pytest.raises(PlannerError):
        await planner.create_plan(user_query=SAMPLE_QUERY)

    assert llm.calls == 1


@pytest.mark.asyncio
async def test_missing_location_is_rejected() -> None:
    llm = MockLLMProvider(payload=_valid_plan_payload(location=""))
    planner = ResearchPlanner(llm, max_retries=0, retry_backoff_seconds=0)

    with pytest.raises(PlannerError):
        await planner.create_plan(user_query="Is this a good place for a cafe?")


@pytest.mark.asyncio
async def test_ambiguous_question_fails_closed() -> None:
    llm = MockLLMProvider(
        payload={
            "business_type": "unknown",
            "location": "somewhere",
            "objective": "general research",
            "target_customer": None,
            "research_tasks": ["demographics"],
        }
    )
    planner = ResearchPlanner(llm, max_retries=0, retry_backoff_seconds=0)

    with pytest.raises(PlannerError):
        await planner.create_plan(user_query="What should I do next?")


@pytest.mark.asyncio
async def test_planner_retry_succeeds_on_second_attempt() -> None:
    llm = MockLLMProvider(
        payloads=[
            {"broken": True},
            _valid_plan_payload(),
        ]
    )
    planner = ResearchPlanner(llm, max_retries=1, retry_backoff_seconds=0)

    plan = await planner.create_plan(user_query=SAMPLE_QUERY)

    assert plan.location == "Sector 62, Noida"
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_graph_planner_integration_with_mock_llm() -> None:
    llm = MockLLMProvider(payload=_valid_plan_payload())
    graph = build_investigation_graph(
        llm=llm,
        deps=ResearchOrchestrationDeps.mock(),
    )
    service = InvestigationService(graph=graph)

    result = await service.run({"user_query": SAMPLE_QUERY})

    assert result.status in {"completed", "partial"}
    assert result.business_type == "cloud kitchen"
    assert result.location == "Sector 62, Noida"
    assert result.target_customer == "office workers"
    assert result.research_plan == [
        "demographics",
        "competition",
        "geography",
        "infrastructure",
        "weather",
    ]
    assert result.metadata["research_plan"]["objective"] == "location evaluation"
    assert "competition" in result.routed_agents
    assert "geography" in result.routed_agents
    assert "weather" in result.routed_agents
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_graph_records_planner_failure() -> None:
    llm = MockLLMProvider(
        payload=_valid_plan_payload(research_tasks=["not_a_real_task"])
    )
    graph = build_investigation_graph(
        llm=llm,
        deps=ResearchOrchestrationDeps.mock(),
    )
    initial = create_initial_state(SAMPLE_QUERY)

    final_state = await graph.ainvoke(initial)

    assert final_state["status"] == "failed"
    assert final_state["validation_errors"]
    assert "planner_failed" in final_state["validation_errors"][0]
    assert final_state["metadata"]["planner_error"]["attempts"] >= 1


def test_research_plan_model_rejects_unsupported_task() -> None:
    with pytest.raises(ValidationError):
        ResearchPlan.model_validate(
            _valid_plan_payload(research_tasks=["demographics", "astrology"])
        )


def test_research_plan_maps_accessibility_alias() -> None:
    plan = ResearchPlan.model_validate(
        _valid_plan_payload(research_tasks=["accessibility", "demographics"])
    )
    assert "geography" in plan.research_tasks
    assert "accessibility" not in plan.research_tasks
