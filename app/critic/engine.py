"""Deterministic critic checks for investigation quality control."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from app.evidence.models import Evidence
from app.models.analysis import AnalysisInsights, CitedStatement
from app.models.critic import CriticIssue, CriticVerdict
from app.scoring.engine import map_score_to_recommendation

_COVERAGE_AGENTS = ("competition", "geography")
_TASK_FOR_AGENT = {
    "competition": "competition",
    "geography": "geography",
    "weather": "weather",
    "government_data": "government_data",
}
_MISSING_TASK_FOR_DIMENSION = {
    "demand": "competition",
    "competition": "competition",
    "accessibility": "geography",
    "infrastructure": "geography",
    "market_indicators": "government_data",
}


def critique_investigation(
    *,
    evidence: Sequence[Evidence],
    contradictions: Sequence[str] | None = None,
    recommendation: str | None = None,
    opportunity_score: float | None = None,
    insights: AnalysisInsights | None = None,
    scorecard: dict[str, Any] | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    location: str | None = None,
    min_confidence: float = 0.3,
    stale_after_hours: float = 72.0,
    now: datetime | None = None,
) -> CriticVerdict:
    """Evaluate coverage, provenance, freshness, and logical support.

    Returns PASS only when there are no error-severity issues. Warnings do not
    fail the critic but still appear in ``issues``.
    """
    items = [item for item in evidence if item.claim_kind != "RECOMMENDATION"]
    current = now or datetime.now(UTC)
    issues: list[CriticIssue] = []

    issues.extend(_check_coverage(items, latitude=latitude, longitude=longitude))
    issues.extend(_check_source_quality(items, min_confidence=min_confidence))
    issues.extend(_check_freshness(items, stale_after_hours, current))
    issues.extend(_check_contradictions(list(contradictions or [])))
    issues.extend(_check_unsupported_claims(items, insights))
    issues.extend(
        _check_logical_consistency(
            recommendation=recommendation,
            opportunity_score=opportunity_score,
        )
    )
    issues.extend(
        _check_missing_critical(
            items,
            recommendation=recommendation,
            scorecard=scorecard or {},
            location=location,
            latitude=latitude,
            longitude=longitude,
        )
    )

    required = _required_research(issues)
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    status = "FAIL" if errors else "PASS"
    confidence = max(0.0, 1.0 - (0.18 * len(errors)) - (0.05 * len(warnings)))
    if not items:
        confidence = min(confidence, 0.2)

    return CriticVerdict(
        status=status,
        confidence=round(confidence, 4),
        issues=issues,
        required_research=required,
    )


def _check_coverage(
    items: Sequence[Evidence],
    *,
    latitude: float | None,
    longitude: float | None,
) -> list[CriticIssue]:
    issues: list[CriticIssue] = []
    by_agent = {item.agent for item in items}
    if "competition" not in by_agent:
        issues.append(
            CriticIssue(
                check="evidence_coverage",
                message="Competition data is insufficient.",
                severity="error",
                research_task="competition",
            )
        )
    has_geo = "geography" in by_agent
    has_coords = latitude is not None and longitude is not None
    if not has_geo and not has_coords:
        issues.append(
            CriticIssue(
                check="evidence_coverage",
                message="Location/geography evidence is insufficient.",
                severity="error",
                research_task="geography",
            )
        )
    elif not has_geo and has_coords:
        issues.append(
            CriticIssue(
                check="evidence_coverage",
                message=(
                    "Coordinates are resolved but the geography agent "
                    "did not contribute evidence."
                ),
                severity="warning",
                research_task="geography",
            )
        )
    if not items:
        issues.append(
            CriticIssue(
                check="evidence_coverage",
                message="No validated evidence is available.",
                severity="error",
            )
        )
    return issues


def _check_source_quality(
    items: Sequence[Evidence],
    *,
    min_confidence: float,
) -> list[CriticIssue]:
    issues: list[CriticIssue] = []
    for item in items:
        if item.source is None or not item.source.name.strip():
            issues.append(
                CriticIssue(
                    check="source_quality",
                    message=f"Evidence {item.evidence_id} is missing a source.",
                    severity="error",
                    research_task=_TASK_FOR_AGENT.get(item.agent),
                )
            )
            continue
        if item.source.reliability == "low":
            issues.append(
                CriticIssue(
                    check="source_quality",
                    message=(
                        f"Evidence {item.evidence_id} has low source reliability."
                    ),
                    severity="warning",
                    research_task=_TASK_FOR_AGENT.get(item.agent),
                )
            )
        if item.confidence < min_confidence:
            issues.append(
                CriticIssue(
                    check="source_quality",
                    message=(
                        f"Evidence {item.evidence_id} confidence "
                        f"{item.confidence} is below {min_confidence}."
                    ),
                    severity="warning",
                    research_task=_TASK_FOR_AGENT.get(item.agent),
                )
            )
    return issues


def _check_freshness(
    items: Sequence[Evidence],
    stale_after_hours: float,
    now: datetime,
) -> list[CriticIssue]:
    issues: list[CriticIssue] = []
    limit = timedelta(hours=stale_after_hours)
    stale_ids: list[str] = []
    for item in items:
        retrieved = item.retrieved_at
        if retrieved.tzinfo is None:
            retrieved = retrieved.replace(tzinfo=UTC)
        current = now if now.tzinfo else now.replace(tzinfo=UTC)
        if current - retrieved > limit:
            stale_ids.append(item.evidence_id)
            issues.append(
                CriticIssue(
                    check="data_freshness",
                    message=(
                        f"Evidence {item.evidence_id} is stale "
                        f"(older than {stale_after_hours:g} hours)."
                    ),
                    severity="warning",
                    research_task=_TASK_FOR_AGENT.get(item.agent),
                )
            )
    if items and len(stale_ids) == len(items):
        issues.append(
            CriticIssue(
                check="data_freshness",
                message="All validated evidence is stale.",
                severity="error",
            )
        )
    return issues


def _check_contradictions(contradictions: Sequence[str]) -> list[CriticIssue]:
    if not contradictions:
        return []
    return [
        CriticIssue(
            check="contradictions",
            message=f"Unresolved contradiction: {summary}",
            severity="error",
        )
        for summary in contradictions
    ]


def _check_unsupported_claims(
    items: Sequence[Evidence],
    insights: AnalysisInsights | None,
) -> list[CriticIssue]:
    if insights is None:
        return []
    known = {item.evidence_id for item in items}
    issues: list[CriticIssue] = []
    groups: list[tuple[str, list[CitedStatement]]] = [
        ("observation", insights.observations),
        ("opportunity", insights.opportunities),
        ("risk", insights.risks),
        ("inferred insight", insights.inferred_insights),
    ]
    for label, statements in groups:
        for statement in statements:
            unknown = [eid for eid in statement.evidence_ids if eid not in known]
            if unknown:
                issues.append(
                    CriticIssue(
                        check="unsupported_claims",
                        message=(
                            f"Unsupported {label} cites unknown evidence "
                            f"IDs: {', '.join(unknown)}"
                        ),
                        severity="error",
                    )
                )
            if label == "inferred insight" and not statement.evidence_ids:
                issues.append(
                    CriticIssue(
                        check="unsupported_claims",
                        message="Inferred insight has no supporting evidence IDs.",
                        severity="error",
                    )
                )
    return issues


def _check_logical_consistency(
    *,
    recommendation: str | None,
    opportunity_score: float | None,
) -> list[CriticIssue]:
    if recommendation is None or opportunity_score is None:
        return []
    if recommendation == "INSUFFICIENT DATA":
        return []
    expected = map_score_to_recommendation(opportunity_score)
    if recommendation != expected:
        return [
            CriticIssue(
                check="logical_consistency",
                message=(
                    f"Recommendation '{recommendation}' is not supported by "
                    f"score {opportunity_score:.2f} (expected '{expected}')."
                ),
                severity="error",
            )
        ]
    return []


def _check_missing_critical(
    items: Sequence[Evidence],
    *,
    recommendation: str | None,
    scorecard: dict[str, Any],
    location: str | None,
    latitude: float | None,
    longitude: float | None,
) -> list[CriticIssue]:
    issues: list[CriticIssue] = []
    if not (location or "").strip() and latitude is None:
        issues.append(
            CriticIssue(
                check="missing_critical_information",
                message="Investigation is missing a location.",
                severity="error",
                research_task="geography",
            )
        )
    critical_missing = list(scorecard.get("critical_missing") or [])
    has_coords = latitude is not None and longitude is not None
    for dimension in critical_missing:
        task = _MISSING_TASK_FOR_DIMENSION.get(str(dimension))
        severity: Literal["error", "warning"] = "error"
        if str(dimension) == "accessibility" and has_coords:
            severity = "warning"
        issues.append(
            CriticIssue(
                check="missing_critical_information",
                message=f"Critical scoring dimension '{dimension}' has no evidence.",
                severity=severity,
                research_task=task,
            )
        )
    if recommendation == "INSUFFICIENT DATA" and not critical_missing and not items:
        issues.append(
            CriticIssue(
                check="missing_critical_information",
                message="Recommendation is INSUFFICIENT DATA with no evidence base.",
                severity="error",
            )
        )
    return issues


def _required_research(issues: Sequence[CriticIssue]) -> list[str]:
    tasks: list[str] = []
    for issue in issues:
        if issue.severity != "error":
            continue
        task = (issue.research_task or "").strip().lower()
        if task and task not in tasks:
            tasks.append(task)
    if not tasks and any(issue.severity == "error" for issue in issues):
        for agent in _COVERAGE_AGENTS:
            if agent not in tasks:
                tasks.append(agent)
    return tasks
