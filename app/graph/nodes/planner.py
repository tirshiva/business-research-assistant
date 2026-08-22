"""Research planner graph node."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.core.exceptions import PlannerError
from app.core.logging import get_logger
from app.graph.deps import ResearchOrchestrationDeps
from app.graph.progress import emit_progress
from app.graph.state import InvestigationState
from app.llm import get_llm_provider
from app.llm.base import LLMProvider
from app.models.research_plan import SUPPORTED_RESEARCH_TASKS
from app.services.planner import ResearchPlanner

logger = get_logger(__name__)


def create_planner_node(
    llm: LLMProvider | None = None,
    deps: ResearchOrchestrationDeps | None = None,
):
    """Build a planner node closure bound to an LLM provider."""

    settings = get_settings()
    provider = llm or get_llm_provider()
    planner = ResearchPlanner(
        provider,
        max_retries=settings.planner_max_retries,
        retry_backoff_seconds=settings.planner_retry_backoff_seconds,
    )

    async def planner_node(state: InvestigationState) -> dict[str, Any]:
        """Generate a ResearchPlan and merge it into investigation state."""
        iteration = int(state.get("iteration") or 0) + 1

        if state.get("status") == "failed":
            logger.info(
                "Skipping planner because prior node failed (id=%s)",
                state.get("investigation_id"),
            )
            return {"iteration": iteration}

        user_query = (state.get("user_query") or "").strip()
        if not user_query:
            error = "Cannot plan research without user_query"
            return {
                "validation_errors": [*(state.get("validation_errors") or []), error],
                "status": "failed",
                "iteration": iteration,
            }

        try:
            plan = await planner.create_plan(
                user_query=user_query,
                business_type=state.get("business_type"),
                location=state.get("location"),
                objective=state.get("objective"),
                target_customer=state.get("target_customer"),
                required_research=list(state.get("required_research") or []),
                critic_issues=list(state.get("critic_issues") or []),
            )
        except PlannerError as exc:
            error = f"planner_failed: {exc.message}"
            logger.error(
                "Planner failed id=%s attempts=%s details=%s",
                state.get("investigation_id"),
                exc.attempts,
                exc.details,
            )
            metadata = dict(state.get("metadata") or {})
            metadata["planner_error"] = {
                "message": exc.message,
                "details": exc.details,
                "attempts": exc.attempts,
            }
            return {
                "validation_errors": [*(state.get("validation_errors") or []), error],
                "status": "failed",
                "iteration": iteration,
                "metadata": metadata,
            }

        metadata = dict(state.get("metadata") or {})
        metadata["research_plan"] = plan.model_dump(mode="json")

        tasks = list(plan.research_tasks)
        for task in state.get("required_research") or []:
            name = str(task).strip().lower()
            if name in SUPPORTED_RESEARCH_TASKS and name not in tasks:
                tasks.append(name)

        if deps is not None:
            await emit_progress(
                deps,
                "record_plan",
                state.get("investigation_id") or "",
                plan=tasks,
                business_type=plan.business_type,
                location=plan.location,
                target_customer=plan.target_customer,
            )

        return {
            "business_type": plan.business_type,
            "location": plan.location,
            "objective": plan.objective,
            "target_customer": plan.target_customer,
            "research_plan": tasks,
            "analysis": ("Research plan created with tasks: " + ", ".join(tasks)),
            "validation_errors": [],
            "status": "planned",
            "iteration": iteration,
            "metadata": metadata,
        }

    return planner_node
