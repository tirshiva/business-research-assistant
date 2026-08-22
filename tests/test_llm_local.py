"""Tests for local LLM dynamic task selection."""

from __future__ import annotations

import pytest

from app.llm.local import LocalLLMProvider
from app.models.research_plan import ResearchPlan


@pytest.mark.asyncio
async def test_local_provider_selects_relevant_tasks_for_cloud_kitchen() -> None:
    llm = LocalLLMProvider()
    plan = await llm.generate_structured(
        system_prompt="plan",
        user_prompt=(
            "Create a plan.\n"
            "User question: Is Sector 62, Noida a good location for a cloud kitchen "
            "targeting office workers?\n"
            "CONTEXT_JSON:\n"
            '{"user_query":"Is Sector 62, Noida a good location for a cloud kitchen '
            'targeting office workers?","business_type":"cloud_kitchen",'
            '"location":"Sector 62, Noida","objective":null,'
            '"target_customer":"office workers"}'
        ),
        response_model=ResearchPlan,
    )

    assert plan.business_type == "cloud kitchen"
    assert plan.location == "Sector 62, Noida"
    assert plan.target_customer == "office workers"
    assert plan.objective == "location evaluation"
    for task in (
        "demographics",
        "competition",
        "geography",
        "infrastructure",
        "weather",
    ):
        assert task in plan.research_tasks


@pytest.mark.asyncio
async def test_local_provider_omits_weather_when_irrelevant() -> None:
    llm = LocalLLMProvider()
    plan = await llm.generate_structured(
        system_prompt="plan",
        user_prompt=(
            "User question: Is Koramangala a good location for a coworking space?\n"
            "CONTEXT_JSON:\n"
            '{"user_query":"Is Koramangala a good location for a coworking space?",'
            '"business_type":"coworking","location":"Koramangala",'
            '"objective":"location evaluation","target_customer":null}'
        ),
        response_model=ResearchPlan,
    )

    assert "weather" not in plan.research_tasks
    assert "demographics" in plan.research_tasks
    assert "competition" in plan.research_tasks
