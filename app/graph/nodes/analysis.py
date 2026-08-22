"""Analysis graph node — insights + deterministic opportunity scoring."""

from __future__ import annotations

from typing import Any

from app.agents.analysis import AnalysisAgent
from app.config import get_settings
from app.core.logging import get_logger
from app.evidence.models import Evidence
from app.graph.deps import ResearchOrchestrationDeps
from app.graph.progress import emit_progress
from app.graph.state import InvestigationState
from app.llm import get_llm_provider
from app.llm.base import LLMProvider
from app.scoring.models import ScoringConfig, ScoringDimension

logger = get_logger(__name__)


def scoring_config_from_settings() -> ScoringConfig:
    """Load scoring weights and critical dimensions from application settings."""
    settings = get_settings()
    weights: dict[ScoringDimension, float] = {
        "demand": settings.score_weight_demand,
        "competition": settings.score_weight_competition,
        "accessibility": settings.score_weight_accessibility,
        "infrastructure": settings.score_weight_infrastructure,
        "market_indicators": settings.score_weight_market_indicators,
        "risk": settings.score_weight_risk,
    }
    critical_raw = [
        part.strip()
        for part in settings.score_critical_dimensions.split(",")
        if part.strip()
    ]
    critical = tuple(item for item in critical_raw if item in weights)
    return ScoringConfig(
        weights=weights,
        critical_dimensions=critical or ("demand", "competition", "accessibility"),
    )


def create_analysis_node(
    llm: LLMProvider | None = None,
    deps: ResearchOrchestrationDeps | None = None,
):
    """Build the analysis node bound to an LLM (insights only) and scoring config."""

    provider = llm or get_llm_provider()
    agent = AnalysisAgent(provider, scoring_config=scoring_config_from_settings())

    async def analysis_node(state: InvestigationState) -> dict[str, Any]:
        iteration = int(state.get("iteration") or 0) + 1
        if state.get("status") == "failed":
            logger.info(
                "Skipping analysis because prior node failed (id=%s)",
                state.get("investigation_id"),
            )
            return {"iteration": iteration}

        evidence = _load_evidence(state.get("evidence") or [])
        metadata = dict(state.get("metadata") or {})
        investigation_id = state.get("investigation_id") or ""
        if deps is not None:
            await emit_progress(deps, "mark_stage", investigation_id, "ANALYZING")

        result = await agent.run(
            evidence,
            business_type=state.get("business_type"),
            location=state.get("location"),
            objective=state.get("objective"),
            contradictions=state.get("contradictions") or [],
            unavailable_dimensions=state.get("unavailable_dimensions") or [],
        )

        metadata["analysis"] = result.insights.model_dump(mode="json")
        metadata["opportunity_scorecard"] = result.scorecard

        logger.info(
            "Analysis node id=%s score=%s recommendation=%s",
            state.get("investigation_id"),
            result.overall_score,
            result.recommendation,
        )
        return {
            "analysis": result.summary_text(),
            "opportunity_score": result.overall_score,
            "recommendation": result.recommendation,
            "confidence": result.confidence,
            "iteration": iteration,
            "metadata": metadata,
        }

    return analysis_node


def _load_evidence(raw_items: list[dict[str, Any]]) -> list[Evidence]:
    loaded: list[Evidence] = []
    for raw in raw_items:
        try:
            loaded.append(Evidence.model_validate(raw))
        except Exception:  # noqa: BLE001
            logger.warning("Skipping invalid evidence payload during analysis")
    return loaded
