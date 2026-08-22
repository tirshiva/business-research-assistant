"""Tests for the critic and self-correction workflow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.config.settings import get_settings
from app.critic import critique_investigation
from app.evidence.service import build_evidence
from app.graph.deps import ResearchOrchestrationDeps
from app.graph.graph import build_investigation_graph
from app.graph.nodes.critic import route_after_critic
from app.graph.state import create_initial_state
from app.llm.base import LLMProvider
from app.models.analysis import AnalysisInsights, CitedStatement
from app.services.investigation import InvestigationService

SAMPLE_QUERY = (
    "Is Sector 62, Noida a good location for a cloud kitchen targeting office workers?"
)


class PlanLLM(LLMProvider):
    name = "plan-mock"

    def __init__(self, tasks: list[str]) -> None:
        self._tasks = tasks
        self.plan_calls = 0

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[Any],
    ) -> Any:
        del system_prompt, user_prompt
        if response_model.__name__ == "ResearchPlan":
            self.plan_calls += 1
        return response_model.model_validate(
            {
                "business_type": "cloud kitchen",
                "location": "Sector 62, Noida",
                "objective": "location evaluation",
                "target_customer": "office workers",
                "research_tasks": self._tasks,
            }
        )


def _item(
    *,
    evidence_id: str,
    agent: str,
    claim: str = "finding",
    value: object | None = None,
    confidence: float = 0.9,
    retrieved_at: datetime | None = None,
) -> object:
    item = build_evidence(
        investigation_id="inv-critic",
        agent=agent,
        claim=claim,
        value=value or {"summary": claim, "data": {}},
        source_name=f"{agent}-source",
        source_url="https://example.test/",
        confidence=confidence,
        reliability="high",
        retrieved_at=retrieved_at,
    )
    return item.model_copy(update={"evidence_id": evidence_id})


def test_critic_fails_when_competition_missing() -> None:
    evidence = [
        _item(evidence_id="e-geo", agent="geography", claim="Resolved location"),
    ]
    verdict = critique_investigation(
        evidence=evidence,
        latitude=28.6,
        longitude=77.3,
        location="Sector 62, Noida",
    )
    assert verdict.status == "FAIL"
    assert "competition" in verdict.required_research
    assert any(
        "Competition data is insufficient." in issue.message for issue in verdict.issues
    )


def test_critic_passes_with_competition_and_location() -> None:
    evidence = [
        _item(evidence_id="e-geo", agent="geography"),
        _item(evidence_id="e-comp", agent="competition"),
    ]
    verdict = critique_investigation(
        evidence=evidence,
        recommendation="PROMISING",
        opportunity_score=7.4,
        latitude=28.6,
        longitude=77.3,
        location="Sector 62, Noida",
    )
    assert verdict.status == "PASS"
    assert verdict.required_research == []
    assert 0.0 <= verdict.confidence <= 1.0


def test_critic_flags_unsupported_claims() -> None:
    evidence = [
        _item(evidence_id="e-geo", agent="geography"),
        _item(evidence_id="e-comp", agent="competition"),
    ]
    insights = AnalysisInsights(
        inferred_insights=[
            CitedStatement(statement="Invented", evidence_ids=["forged-id"])
        ]
    )
    verdict = critique_investigation(
        evidence=evidence,
        insights=insights,
        latitude=28.6,
        longitude=77.3,
        location="Noida",
    )
    assert verdict.status == "FAIL"
    assert any(issue.check == "unsupported_claims" for issue in verdict.issues)


def test_critic_flags_logical_inconsistency() -> None:
    evidence = [
        _item(evidence_id="e-geo", agent="geography"),
        _item(evidence_id="e-comp", agent="competition"),
    ]
    verdict = critique_investigation(
        evidence=evidence,
        recommendation="STRONG OPPORTUNITY",
        opportunity_score=4.0,
        latitude=28.6,
        longitude=77.3,
        location="Noida",
    )
    assert verdict.status == "FAIL"
    assert any(issue.check == "logical_consistency" for issue in verdict.issues)


def test_critic_flags_stale_and_contradictions() -> None:
    stale = _item(
        evidence_id="e-old",
        agent="competition",
        retrieved_at=datetime.now(UTC) - timedelta(hours=200),
    )
    verdict = critique_investigation(
        evidence=[stale, _item(evidence_id="e-geo", agent="geography")],
        contradictions=["FACT values disagree"],
        latitude=28.6,
        longitude=77.3,
        location="Noida",
        stale_after_hours=72,
    )
    assert verdict.status == "FAIL"
    checks = {issue.check for issue in verdict.issues}
    assert "contradictions" in checks
    assert "data_freshness" in checks


def test_route_after_critic_cycles_on_fail() -> None:
    state = create_initial_state(SAMPLE_QUERY)
    state["critic_status"] = "FAIL"
    assert route_after_critic(state) == "planner"

    state["metadata"] = {"max_research_iterations_reached": True}
    assert route_after_critic(state) == "end"

    state["metadata"] = {}
    state["critic_status"] = "PASS"
    assert route_after_critic(state) == "end"


@pytest.mark.asyncio
async def test_graph_self_corrects_missing_competition() -> None:
    deps = ResearchOrchestrationDeps.mock()
    graph = build_investigation_graph(
        llm=PlanLLM(["weather"]),
        deps=deps,
    )
    final_state = await graph.ainvoke(
        create_initial_state(SAMPLE_QUERY),
        {"recursion_limit": 50},
    )

    agents_run = [item["agent"] for item in final_state["agent_runs"]]
    assert agents_run.count("weather") == 1
    assert agents_run.count("competition") == 1
    assert final_state["critic_status"] == "PASS"
    assert final_state["research_iteration"] >= 2
    public = final_state["metadata"]["critic"]
    assert public["status"] == "PASS"
    assert "required_research" in public


@pytest.mark.asyncio
async def test_graph_halts_after_max_research_iterations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_RESEARCH_ITERATIONS", "2")
    get_settings.cache_clear()
    deps = ResearchOrchestrationDeps.mock(with_failures={"competition"})
    graph = build_investigation_graph(
        llm=PlanLLM(["weather", "geography", "competition"]),
        deps=deps,
    )
    try:
        final_state = await graph.ainvoke(
            create_initial_state(SAMPLE_QUERY),
            {"recursion_limit": 50},
        )
    finally:
        get_settings.cache_clear()

    assert final_state["recommendation"] == "INSUFFICIENT DATA"
    assert final_state["metadata"].get("max_research_iterations_reached") is True
    assert deps.competition_agent.run.await_count == 2
    assert final_state["research_iteration"] == 2
    assert final_state["critic_status"] == "FAIL"


@pytest.mark.asyncio
async def test_investigation_service_converges_to_pass() -> None:
    service = InvestigationService(
        graph=build_investigation_graph(
            llm=PlanLLM(["weather", "geography", "competition"]),
            deps=ResearchOrchestrationDeps.mock(),
        )
    )
    result = await service.run({"user_query": SAMPLE_QUERY})
    assert result.critic_status == "PASS"
    assert result.recommendation != "INSUFFICIENT DATA"
    assert result.metadata["critic"]["status"] == "PASS"
