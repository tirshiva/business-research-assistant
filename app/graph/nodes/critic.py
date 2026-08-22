"""Critic graph node — quality control before the final report."""

from __future__ import annotations

from typing import Any, Literal

from app.config import get_settings
from app.core.logging import get_logger
from app.critic import critique_investigation
from app.evidence.models import Evidence
from app.graph.state import InvestigationState
from app.models.analysis import AnalysisInsights

logger = get_logger(__name__)

CriticRoute = Literal["planner", "end"]


def create_critic_node():
    """Build the critic node. Settings are read per invocation."""

    async def critic_node(state: InvestigationState) -> dict[str, Any]:
        graph_iteration = int(state.get("iteration") or 0) + 1
        metadata = dict(state.get("metadata") or {})
        settings = get_settings()
        max_iterations = max(1, int(settings.max_research_iterations))
        research_iteration = int(state.get("research_iteration") or 0)

        if state.get("status") == "failed":
            logger.info(
                "Skipping critic because investigation failed (id=%s)",
                state.get("investigation_id"),
            )
            return {
                "iteration": graph_iteration,
                "critic_status": "FAIL",
                "critic_issues": ["Investigation failed before critic evaluation"],
                "required_research": [],
            }

        evidence = _load_evidence(state.get("evidence") or [])
        insights = _load_insights(metadata.get("analysis"))
        scorecard = metadata.get("opportunity_scorecard") or {}
        if not isinstance(scorecard, dict):
            scorecard = {}

        verdict = critique_investigation(
            evidence=evidence,
            contradictions=state.get("contradictions") or [],
            recommendation=state.get("recommendation"),
            opportunity_score=state.get("opportunity_score"),
            insights=insights,
            scorecard=scorecard,
            latitude=state.get("latitude"),
            longitude=state.get("longitude"),
            location=state.get("location"),
            min_confidence=settings.evidence_min_confidence,
            stale_after_hours=settings.evidence_stale_after_hours,
        )

        halt = verdict.status == "FAIL" and research_iteration >= max_iterations
        recommendation = state.get("recommendation")
        required = list(verdict.required_research)
        if halt:
            recommendation = "INSUFFICIENT DATA"
            required = []
            metadata["max_research_iterations_reached"] = True
            logger.warning(
                "Critic halt id=%s research_iteration=%s max=%s",
                state.get("investigation_id"),
                research_iteration,
                max_iterations,
            )

        metadata["critic"] = verdict.public_dict()
        metadata["critic_details"] = verdict.model_dump(mode="json")
        metadata["research_iteration"] = research_iteration

        logger.info(
            "Critic id=%s status=%s confidence=%s required=%s halt=%s",
            state.get("investigation_id"),
            verdict.status,
            verdict.confidence,
            required,
            halt,
        )

        updates: dict[str, Any] = {
            "critic_status": verdict.status,
            "critic_confidence": verdict.confidence,
            "critic_issues": [issue.message for issue in verdict.issues],
            "required_research": required,
            "iteration": graph_iteration,
            "metadata": metadata,
        }
        if halt:
            updates["recommendation"] = recommendation
            updates["status"] = "partial"
        return updates

    return critic_node


def route_after_critic(state: InvestigationState) -> CriticRoute:
    """Cyclic edge: FAIL re-enters the planner; PASS / halt / failed end."""
    if state.get("status") == "failed":
        return "end"
    metadata = state.get("metadata") or {}
    if metadata.get("max_research_iterations_reached"):
        return "end"
    if state.get("critic_status") == "FAIL":
        return "planner"
    return "end"


def _load_evidence(raw_items: list[dict[str, Any]]) -> list[Evidence]:
    loaded: list[Evidence] = []
    for raw in raw_items:
        try:
            loaded.append(Evidence.model_validate(raw))
        except Exception:  # noqa: BLE001
            logger.warning("Skipping invalid evidence payload during critic")
    return loaded


def _load_insights(raw: object) -> AnalysisInsights | None:
    if not isinstance(raw, dict):
        return None
    try:
        return AnalysisInsights.model_validate(raw)
    except Exception:  # noqa: BLE001
        return None
