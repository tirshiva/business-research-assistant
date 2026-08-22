"""Research planner service that produces a validated ResearchPlan via an LLM."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.core.exceptions import (
    LLMError,
    LLMStructuredOutputError,
    PlannerError,
)
from app.core.logging import get_logger
from app.llm.base import LLMProvider
from app.models.research_plan import ResearchPlan

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """
You are the research planner for an India business location investigation agent.
Return ONLY a structured ResearchPlan object.
Select only relevant research_tasks from:
demographics, competition, geography, infrastructure, weather,
government_data, documents.
Do not include irrelevant tasks (for example, omit weather unless
climate or logistics matter).
""".strip()


class ResearchPlanner:
    """Convert an analyzed investigation into a validated ResearchPlan."""

    def __init__(
        self,
        llm: LLMProvider,
        *,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.25,
    ) -> None:
        self._llm = llm
        self._max_retries = max(0, max_retries)
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    async def create_plan(
        self,
        *,
        user_query: str,
        business_type: str | None = None,
        location: str | None = None,
        objective: str | None = None,
        target_customer: str | None = None,
    ) -> ResearchPlan:
        """Call the LLM with retries and return a validated ResearchPlan."""
        user_prompt = self._build_user_prompt(
            user_query=user_query,
            business_type=business_type,
            location=location,
            objective=objective,
            target_customer=target_customer,
        )

        attempts = self._max_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                plan = await self._llm.generate_structured(
                    system_prompt=PLANNER_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    response_model=ResearchPlan,
                )
                self._assert_plan_usable(plan, user_query=user_query)
                logger.info(
                    "Research plan created provider=%s tasks=%s attempt=%s",
                    self._llm.name,
                    plan.research_tasks,
                    attempt,
                )
                return plan
            except (
                LLMStructuredOutputError,
                LLMError,
                PlannerError,
                ValueError,
            ) as exc:
                last_error = exc
                logger.warning(
                    "Planner attempt %s/%s failed: %s",
                    attempt,
                    attempts,
                    exc,
                )
                if attempt < attempts and self._retry_backoff_seconds:
                    await asyncio.sleep(self._retry_backoff_seconds * attempt)

        raise PlannerError(
            "Failed to produce a valid research plan after retries",
            details=str(last_error) if last_error else None,
            attempts=attempts,
        ) from last_error

    @staticmethod
    def _build_user_prompt(
        *,
        user_query: str,
        business_type: str | None,
        location: str | None,
        objective: str | None,
        target_customer: str | None,
    ) -> str:
        context: dict[str, Any] = {
            "user_query": user_query,
            "business_type": business_type,
            "location": location,
            "objective": objective,
            "target_customer": target_customer,
        }
        return (
            "Create a structured research plan for the following investigation.\n"
            f"User question: {user_query}\n"
            f"CONTEXT_JSON:\n{json.dumps(context, ensure_ascii=True)}"
        )

    @staticmethod
    def _assert_plan_usable(plan: ResearchPlan, *, user_query: str) -> None:
        """Reject plans that are structurally valid but operationally unusable."""
        if not plan.location.strip():
            raise PlannerError("Research plan is missing a location")
        if not plan.business_type.strip():
            raise PlannerError("Research plan is missing a business_type")
        if not plan.research_tasks:
            raise PlannerError("Research plan has no research_tasks")
        # Ambiguous questions often leave both business and place unresolved.
        if plan.business_type.lower() in {"unknown", "n/a", "none"}:
            raise PlannerError(
                "Research plan business_type is too ambiguous",
                details=user_query,
            )
