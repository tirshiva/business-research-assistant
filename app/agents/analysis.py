"""Analysis agent: qualitative insights from validated evidence only."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, ClassVar

from app.agents.insight_builder import build_deterministic_insights
from app.core.exceptions import LLMError
from app.core.logging import get_logger
from app.evidence.models import Evidence
from app.llm.base import LLMProvider
from app.models.analysis import AnalysisInsights, AnalysisResult, CitedStatement
from app.scoring import ScoringConfig, score_opportunity

logger = get_logger(__name__)

ANALYSIS_SYSTEM_PROMPT = """
You are the business analysis agent for an India location investigation.
You receive ONLY validated evidence items (id, agent, claim, value, confidence).
Produce qualitative insights: observations, opportunities, risks, unknowns,
and inferred_insights.
Every inferred insight MUST cite supporting evidence_ids from the provided list.
Do not invent numerical opportunity scores, weights, or recommendations.
Do not cite evidence IDs that were not provided.
Unknowns may have empty evidence_ids.
""".strip()


class AnalysisAgent:
    """Transform validated evidence into cited insights; scoring is separate."""

    name: ClassVar[str] = "analysis"

    def __init__(
        self,
        llm: LLMProvider | None = None,
        *,
        scoring_config: ScoringConfig | None = None,
    ) -> None:
        self._llm = llm
        self._scoring_config = scoring_config or ScoringConfig()

    async def run(
        self,
        evidence: Sequence[Evidence],
        *,
        business_type: str | None = None,
        location: str | None = None,
        objective: str | None = None,
        contradictions: Sequence[str] | None = None,
        unavailable_dimensions: Sequence[str] | None = None,
    ) -> AnalysisResult:
        """Analyze validated evidence and attach a deterministic scorecard."""
        validated = [item for item in evidence if item.claim_kind != "RECOMMENDATION"]
        known_ids = {item.evidence_id for item in validated}

        insights = await self._generate_insights(
            validated,
            business_type=business_type,
            location=location,
            objective=objective,
            unavailable_dimensions=unavailable_dimensions,
        )
        insights = _sanitize_citations(insights, known_ids)

        scorecard = score_opportunity(
            validated,
            self._scoring_config,
            contradictions=contradictions,
            unavailable_dimensions=unavailable_dimensions,
        )
        confidence = _scorecard_confidence(scorecard.dimensions)

        logger.info(
            "Analysis complete score=%s recommendation=%s evidence=%s",
            scorecard.overall_score,
            scorecard.recommendation,
            len(validated),
        )
        return AnalysisResult(
            insights=insights,
            overall_score=scorecard.overall_score,
            recommendation=scorecard.recommendation,
            confidence=confidence,
            scorecard=scorecard.model_dump(mode="json"),
        )

    async def _generate_insights(
        self,
        evidence: Sequence[Evidence],
        *,
        business_type: str | None,
        location: str | None,
        objective: str | None,
        unavailable_dimensions: Sequence[str] | None,
    ) -> AnalysisInsights:
        fallback = build_deterministic_insights(
            evidence,
            business_type=business_type,
            location=location,
            unavailable_dimensions=unavailable_dimensions,
        )
        if self._llm is None:
            return fallback

        payload = {
            "business_type": business_type,
            "location": location,
            "objective": objective,
            "unavailable_dimensions": list(unavailable_dimensions or []),
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "agent": item.agent,
                    "claim": item.claim,
                    "value": item.value,
                    "confidence": item.confidence,
                    "claim_kind": item.claim_kind,
                }
                for item in evidence
            ],
        }
        user_prompt = (
            "Analyze the validated evidence. Return AnalysisInsights only.\n"
            f"CONTEXT_JSON:\n{json.dumps(payload, default=str)}"
        )
        try:
            return await self._llm.generate_structured(
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=AnalysisInsights,
            )
        except (LLMError, Exception) as exc:  # noqa: BLE001
            logger.warning("Analysis LLM failed; using deterministic insights: %s", exc)
            return fallback


def _sanitize_citations(
    insights: AnalysisInsights,
    known_ids: set[str],
) -> AnalysisInsights:
    """Drop unknown evidence IDs; inferred insights must keep at least one."""

    def clean(
        items: list[CitedStatement],
        *,
        require_ids: bool,
    ) -> list[CitedStatement]:
        cleaned: list[CitedStatement] = []
        for item in items:
            ids = [eid for eid in item.evidence_ids if eid in known_ids]
            if require_ids and not ids:
                continue
            cleaned.append(item.model_copy(update={"evidence_ids": ids}))
        return cleaned

    return AnalysisInsights(
        observations=clean(insights.observations, require_ids=False),
        opportunities=clean(insights.opportunities, require_ids=False),
        risks=clean(insights.risks, require_ids=False),
        unknowns=clean(insights.unknowns, require_ids=False),
        inferred_insights=clean(insights.inferred_insights, require_ids=True),
    )


def _scorecard_confidence(dimensions: list[Any]) -> float:
    scored = [
        dim.confidence for dim in dimensions if not getattr(dim, "missing", False)
    ]
    if not scored:
        return 0.0
    return round(sum(scored) / len(scored), 4)
