"""Deterministic qualitative insights derived only from validated evidence."""

from __future__ import annotations

from collections.abc import Sequence

from app.evidence.models import Evidence
from app.models.analysis import AnalysisInsights, CitedStatement


def build_deterministic_insights(
    evidence: Sequence[Evidence],
    *,
    business_type: str | None = None,
    location: str | None = None,
    unavailable_dimensions: Sequence[str] | None = None,
) -> AnalysisInsights:
    """Build cited observations / opportunities / risks / unknowns / inferences.

    Used by the local LLM provider and as a fallback when structured generation
    fails. Does not invent numerical scores.
    """
    items = [item for item in evidence if item.claim_kind != "RECOMMENDATION"]
    by_agent: dict[str, list[Evidence]] = {}
    for item in items:
        by_agent.setdefault(item.agent, []).append(item)

    observations: list[CitedStatement] = []
    for item in items:
        summary = _summary(item)
        observations.append(
            CitedStatement(
                statement=f"{item.agent}: {item.claim} — {summary}",
                evidence_ids=[item.evidence_id],
                kind="observation",
            )
        )

    opportunities: list[CitedStatement] = []
    geography = by_agent.get("geography") or []
    if geography:
        opportunities.append(
            CitedStatement(
                statement=(
                    "Location can be resolved geographically"
                    + (f" for {location}" if location else "")
                    + ", supporting site evaluation."
                ),
                evidence_ids=[item.evidence_id for item in geography],
                kind="opportunity",
            )
        )
    competition = by_agent.get("competition") or []
    if 1 <= len(competition) <= 4:
        label = business_type or "the proposed business"
        opportunities.append(
            CitedStatement(
                statement=(
                    f"Moderate nearby competition ({len(competition)} listing(s)) "
                    f"suggests existing demand for {label} without extreme saturation."
                ),
                evidence_ids=[item.evidence_id for item in competition],
                kind="opportunity",
            )
        )
    government = by_agent.get("government_data") or []
    if government:
        opportunities.append(
            CitedStatement(
                statement=(
                    "Public catalog datasets are available to inform market "
                    "and regulatory context."
                ),
                evidence_ids=[item.evidence_id for item in government],
                kind="opportunity",
            )
        )

    risks: list[CitedStatement] = []
    if len(competition) >= 5:
        risks.append(
            CitedStatement(
                statement=(
                    f"High competitor density ({len(competition)} listings) "
                    "may compress margins and raise customer-acquisition cost."
                ),
                evidence_ids=[item.evidence_id for item in competition],
                kind="risk",
            )
        )
    weather = by_agent.get("weather") or []
    if weather:
        risks.append(
            CitedStatement(
                statement=(
                    "Weather conditions may affect outdoor operations, "
                    "footfall, or delivery reliability."
                ),
                evidence_ids=[item.evidence_id for item in weather],
                kind="risk",
            )
        )
    low_conf = [item for item in items if item.confidence < 0.5]
    if low_conf:
        risks.append(
            CitedStatement(
                statement=(
                    f"{len(low_conf)} evidence item(s) have low confidence "
                    "and should be treated cautiously."
                ),
                evidence_ids=[item.evidence_id for item in low_conf],
                kind="risk",
            )
        )

    unknowns: list[CitedStatement] = []
    for dimension in unavailable_dimensions or []:
        unknowns.append(
            CitedStatement(
                statement=f"No validated evidence was collected for '{dimension}'.",
                evidence_ids=[],
                kind="unknown",
            )
        )
    if "competition" not in by_agent:
        unknowns.append(
            CitedStatement(
                statement="Competitive intensity is unknown (no competition evidence).",
                evidence_ids=[],
                kind="unknown",
            )
        )
    if "government_data" not in by_agent:
        unknowns.append(
            CitedStatement(
                statement=(
                    "Official market / demographic indicators are unknown "
                    "(no government catalog evidence)."
                ),
                evidence_ids=[],
                kind="unknown",
            )
        )
    if not items:
        unknowns.append(
            CitedStatement(
                statement="No validated evidence is available for analysis.",
                evidence_ids=[],
                kind="unknown",
            )
        )

    inferred: list[CitedStatement] = []
    if geography and competition:
        inferred.append(
            CitedStatement(
                statement=(
                    "The site is a geographically identifiable market with "
                    "observable local competitors, so a location decision can "
                    "be evidence-based rather than purely speculative."
                ),
                evidence_ids=[
                    *[item.evidence_id for item in geography],
                    *[item.evidence_id for item in competition],
                ],
                kind="inferred",
            )
        )
    elif items:
        inferred.append(
            CitedStatement(
                statement=(
                    "Available validated findings provide a partial picture of "
                    "the location; additional critical evidence would strengthen "
                    "the recommendation."
                ),
                evidence_ids=[item.evidence_id for item in items],
                kind="inferred",
            )
        )

    return AnalysisInsights(
        observations=observations,
        opportunities=opportunities,
        risks=risks,
        unknowns=unknowns,
        inferred_insights=inferred,
    )


def _summary(item: Evidence) -> str:
    value = item.value
    if isinstance(value, dict):
        summary = value.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    return str(value)
