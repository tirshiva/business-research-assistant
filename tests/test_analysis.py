"""Tests for the analysis agent and graph analysis node."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.agents.analysis import AnalysisAgent
from app.graph.deps import ResearchOrchestrationDeps
from app.graph.graph import build_investigation_graph
from app.graph.state import create_initial_state
from app.llm.base import LLMProvider
from app.llm.local import LocalLLMProvider
from app.models.analysis import AnalysisInsights, CitedStatement
from app.scoring import score_opportunity
from tests.test_scoring import _full_set

SAMPLE_QUERY = (
    "Is Sector 62, Noida a good location for a cloud kitchen targeting office workers?"
)


class InsightLLM(LLMProvider):
    """Returns qualitative insights only — never a numerical score."""

    name = "insight-mock"

    def __init__(self, statement: str = "Custom observation") -> None:
        self.statement = statement
        self.calls = 0

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[Any],
    ) -> Any:
        del system_prompt, user_prompt
        self.calls += 1
        if response_model is AnalysisInsights:
            return AnalysisInsights(
                observations=[
                    CitedStatement(
                        statement=self.statement,
                        evidence_ids=["e-geo"],
                    )
                ],
                opportunities=[],
                risks=[],
                unknowns=[],
                inferred_insights=[
                    CitedStatement(
                        statement="Demand exists near resolved competitors.",
                        evidence_ids=["e-geo", "e-comp"],
                    )
                ],
            )
        raise AssertionError(f"unexpected model {response_model}")


def test_inferred_insights_require_evidence_ids() -> None:
    with pytest.raises(ValidationError):
        AnalysisInsights(
            observations=[],
            opportunities=[],
            risks=[],
            unknowns=[],
            inferred_insights=[
                CitedStatement(statement="Guess with no sources", evidence_ids=[])
            ],
        )


@pytest.mark.asyncio
async def test_analysis_agent_cites_only_validated_evidence() -> None:
    evidence = _full_set()
    result = await AnalysisAgent(InsightLLM()).run(evidence)

    known = {item.evidence_id for item in evidence}
    for group in (
        result.insights.observations,
        result.insights.opportunities,
        result.insights.risks,
        result.insights.inferred_insights,
    ):
        for item in group:
            assert set(item.evidence_ids) <= known
    for item in result.insights.inferred_insights:
        assert item.evidence_ids


@pytest.mark.asyncio
async def test_llm_cannot_change_numerical_score() -> None:
    evidence = _full_set()
    python_score = score_opportunity(evidence).overall_score

    first = await AnalysisAgent(InsightLLM("alpha")).run(evidence)
    second = await AnalysisAgent(InsightLLM("beta")).run(evidence)

    assert first.overall_score == second.overall_score == python_score
    assert first.insights.observations[0].statement == "alpha"
    assert second.insights.observations[0].statement == "beta"
    assert first.scorecard["overall_score"] == python_score


@pytest.mark.asyncio
async def test_unknown_llm_citations_are_stripped() -> None:
    class BadCiteLLM(LLMProvider):
        name = "bad-cite"

        async def generate_structured(self, **kwargs: Any) -> Any:
            del kwargs
            return AnalysisInsights(
                observations=[
                    CitedStatement(statement="ok", evidence_ids=["e-geo", "forged"])
                ],
                inferred_insights=[
                    CitedStatement(statement="drop me", evidence_ids=["forged"]),
                    CitedStatement(statement="keep me", evidence_ids=["e-comp"]),
                ],
            )

    result = await AnalysisAgent(BadCiteLLM()).run(_full_set())
    assert result.insights.observations[0].evidence_ids == ["e-geo"]
    statements = [item.statement for item in result.insights.inferred_insights]
    assert "drop me" not in statements
    assert "keep me" in statements


@pytest.mark.asyncio
async def test_graph_analysis_sets_score_and_recommendation() -> None:
    graph = build_investigation_graph(
        llm=LocalLLMProvider(),
        deps=ResearchOrchestrationDeps.mock(),
    )
    final_state = await graph.ainvoke(create_initial_state(SAMPLE_QUERY))

    assert isinstance(final_state["opportunity_score"], float)
    assert 0.0 <= final_state["opportunity_score"] <= 10.0
    assert final_state["recommendation"] in {
        "STRONG OPPORTUNITY",
        "PROMISING",
        "PROCEED WITH CAUTION",
        "WEAK OPPORTUNITY",
        "LOW OPPORTUNITY",
        "INSUFFICIENT DATA",
    }
    assert "Observations:" in (final_state["analysis"] or "")
    scorecard = final_state["metadata"]["opportunity_scorecard"]
    assert scorecard["formula"]
    assert scorecard["dimensions"]
    second = await graph.ainvoke(create_initial_state(SAMPLE_QUERY))
    assert second["opportunity_score"] == final_state["opportunity_score"]
