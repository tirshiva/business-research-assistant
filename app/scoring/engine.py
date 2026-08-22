"""Deterministic opportunity scoring (Python only — never LLM-invented)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from app.evidence.models import Evidence
from app.scoring.models import (
    DEFAULT_CRITICAL_DIMENSIONS,
    DimensionScore,
    Recommendation,
    Scorecard,
    ScoringConfig,
    ScoringDimension,
)

_COMPETITION_LEVELS = {"LOW": 8.5, "MEDIUM": 5.5, "HIGH": 2.5}
_COMMERCIAL_TOKENS = (
    "office",
    "sector",
    "commercial",
    "it park",
    "tech",
    "noida",
    "gurugram",
    "bangalore",
    "bengaluru",
    "mumbai",
    "hyderabad",
    "pune",
)


def map_score_to_recommendation(score: float) -> Recommendation:
    """Map a 0-10 overall score onto the fixed recommendation bands."""
    value = float(score)
    if value >= 8.5:
        return "STRONG OPPORTUNITY"
    if value >= 7.0:
        return "PROMISING"
    if value >= 5.0:
        return "PROCEED WITH CAUTION"
    if value >= 3.0:
        return "WEAK OPPORTUNITY"
    return "LOW OPPORTUNITY"


def score_opportunity(
    evidence: Sequence[Evidence],
    config: ScoringConfig | None = None,
    *,
    contradictions: Sequence[str] | None = None,
    unavailable_dimensions: Sequence[str] | None = None,
) -> Scorecard:
    """Compute a weighted 0-10 score from validated evidence only.

    Numerical values are produced exclusively by this function. The same
    evidence + config always yields the same ``overall_score``.
    """
    cfg = config or ScoringConfig()
    weights = cfg.normalized_weights()
    items = [item for item in evidence if item.claim_kind != "RECOMMENDATION"]
    items = sorted(items, key=lambda item: item.evidence_id)
    contradiction_list = list(contradictions or [])
    unavailable = list(unavailable_dimensions or [])

    by_agent: dict[str, list[Evidence]] = {}
    for item in items:
        by_agent.setdefault(item.agent, []).append(item)

    dimensions = [
        _score_demand(by_agent, weights["demand"]),
        _score_competition(by_agent, weights["competition"]),
        _score_accessibility(by_agent, weights["accessibility"]),
        _score_infrastructure(by_agent, weights["infrastructure"]),
        _score_market_indicators(by_agent, weights["market_indicators"]),
        _score_risk(
            items,
            weights["risk"],
            contradictions=contradiction_list,
            unavailable=unavailable,
        ),
    ]

    available = [dim for dim in dimensions if not dim.missing]
    missing = [dim.dimension for dim in dimensions if dim.missing]
    critical = tuple(cfg.critical_dimensions) or DEFAULT_CRITICAL_DIMENSIONS
    critical_missing = [name for name in critical if name in missing]

    if available:
        total = Decimal("0")
        weight_sum = Decimal("0")
        for dim in available:
            total += _decimal(dim.score) * _decimal(dim.weight)
            weight_sum += _decimal(dim.weight)
        overall = _quantize(total / weight_sum)
        weight_sum_used = _quantize(weight_sum, places=4)
        formula = (
            "overall = sum(score_i * weight_i) / sum(weight_i) "
            "for dimensions with supporting evidence; "
            + " + ".join(
                f"({dim.dimension}:{dim.score}*{dim.weight})" for dim in available
            )
            + f" / {weight_sum_used}"
        )
    else:
        overall = 0.0
        weight_sum_used = 0.0
        formula = "overall = 0 (no scored dimensions)"

    if critical_missing:
        recommendation: Recommendation = "INSUFFICIENT DATA"
    else:
        recommendation = map_score_to_recommendation(overall)

    evidence_ids = [item.evidence_id for item in items]
    return Scorecard(
        dimensions=dimensions,
        overall_score=overall,
        recommendation=recommendation,
        weight_sum_used=weight_sum_used,
        formula=formula,
        missing_dimensions=missing,
        critical_missing=critical_missing,
        evidence_ids=evidence_ids,
    )


def _score_demand(
    by_agent: dict[str, list[Evidence]],
    weight: float,
) -> DimensionScore:
    supporting: list[Evidence] = []
    parts: list[float] = []
    notes: list[str] = []

    competition = by_agent.get("competition") or []
    if competition:
        supporting.extend(competition)
        n = len(competition)
        parts.append(_clamp(4.0 + min(4.0, n * 0.8), 0.0, 8.5))
        notes.append(f"demand proxy from {n} competitor listing(s)")

    government = by_agent.get("government_data") or []
    if government:
        supporting.extend(government)
        parts.append(_clamp(5.5 + min(2.5, len(government) * 0.7), 0.0, 8.5))
        notes.append(f"{len(government)} government catalog signal(s)")

    geography = by_agent.get("geography") or []
    commercial = [item for item in geography if _looks_commercial(item)]
    if commercial:
        supporting.extend(commercial)
        parts.append(7.0)
        notes.append("commercial/urban geography signal")

    if not parts:
        return _missing("demand", weight)

    return _dimension(
        "demand",
        score=_mean(parts),
        weight=weight,
        evidence=supporting,
        rationale="; ".join(notes) or "demand inferred from validated evidence",
    )


def _score_competition(
    by_agent: dict[str, list[Evidence]],
    weight: float,
) -> DimensionScore:
    items = by_agent.get("competition") or []
    if not items:
        return _missing("competition", weight)

    level_scores = [_competition_level(item) for item in items]
    explicit = [value for value in level_scores if value is not None]
    distances = [
        dist
        for item in items
        if (dist := _nested_float(item, "distance_km")) is not None
    ]

    if explicit:
        score = _mean(explicit)
        note = f"explicit competition level(s) averaged to {score:.2f}"
    else:
        n = len(items)
        base = 10.0 - min(8.0, n * 1.2)
        distance_bonus = 0.0
        if distances:
            distance_bonus = min(1.5, _mean(distances) * 0.5)
        score = _clamp(base + distance_bonus, 0.0, 10.0)
        note = (
            f"{n} nearby competitor(s); distance bonus {distance_bonus:.2f} "
            f"(higher score = less saturated)"
        )

    return _dimension(
        "competition",
        score=score,
        weight=weight,
        evidence=items,
        rationale=note,
    )


def _score_accessibility(
    by_agent: dict[str, list[Evidence]],
    weight: float,
) -> DimensionScore:
    items = by_agent.get("geography") or []
    if not items:
        return _missing("accessibility", weight)

    score = 6.0
    notes = [f"{len(items)} geography finding(s)"]
    if any(_has_coordinates(item) for item in items):
        score += 1.5
        notes.append("resolved coordinates")
    if any(_has_address(item) for item in items):
        score += 1.0
        notes.append("resolved address")
    if any(_looks_commercial(item) for item in items):
        score += 0.5
        notes.append("urban/commercial context")

    return _dimension(
        "accessibility",
        score=_clamp(score, 0.0, 10.0),
        weight=weight,
        evidence=items,
        rationale="; ".join(notes),
    )


def _score_infrastructure(
    by_agent: dict[str, list[Evidence]],
    weight: float,
) -> DimensionScore:
    weather = by_agent.get("weather") or []
    geography = by_agent.get("geography") or []
    government = by_agent.get("government_data") or []
    supporting = [*weather, *geography, *government]
    if not supporting:
        return _missing("infrastructure", weight)

    parts: list[float] = []
    notes: list[str] = []

    temps = [
        temp
        for item in weather
        if (temp := _nested_float(item, "temperature_c")) is not None
    ]
    if temps:
        temp = _mean(temps)
        if 18.0 <= temp <= 32.0:
            parts.append(8.0)
        elif 10.0 <= temp <= 38.0:
            parts.append(6.0)
        else:
            parts.append(4.0)
        notes.append(f"operating temperature {temp:.1f}C")
    elif weather:
        parts.append(6.0)
        notes.append("weather evidence present without temperature")

    if geography:
        parts.append(6.5)
        notes.append("location context available")
    if government:
        parts.append(6.0)
        notes.append("public dataset coverage")

    return _dimension(
        "infrastructure",
        score=_mean(parts) if parts else 5.0,
        weight=weight,
        evidence=supporting,
        rationale="; ".join(notes) or "infrastructure inferred from evidence",
    )


def _score_market_indicators(
    by_agent: dict[str, list[Evidence]],
    weight: float,
) -> DimensionScore:
    items = by_agent.get("government_data") or []
    if not items:
        return _missing("market_indicators", weight)

    n = len(items)
    score = _clamp(5.0 + min(4.0, n * 1.5), 0.0, 9.0)
    return _dimension(
        "market_indicators",
        score=score,
        weight=weight,
        evidence=items,
        rationale=f"{n} government/market catalog finding(s)",
    )


def _score_risk(
    items: Sequence[Evidence],
    weight: float,
    *,
    contradictions: Sequence[str],
    unavailable: Sequence[str],
) -> DimensionScore:
    if not items:
        return _missing("risk", weight)

    score = 8.0
    notes = ["base risk favorability 8.0"]
    score -= min(3.0, 1.5 * len(contradictions))
    if contradictions:
        notes.append(f"{len(contradictions)} contradiction(s)")

    low_conf = [item for item in items if item.confidence < 0.5]
    score -= min(2.0, 0.5 * len(low_conf))
    if low_conf:
        notes.append(f"{len(low_conf)} low-confidence item(s)")

    temps = [
        temp
        for item in items
        if (temp := _nested_float(item, "temperature_c")) is not None
    ]
    if temps and (min(temps) < 10.0 or max(temps) > 38.0):
        score -= 2.0
        notes.append("extreme temperature")

    competition_n = sum(1 for item in items if item.agent == "competition")
    if competition_n >= 8:
        score -= 1.0
        notes.append("crowded competitive set")

    score -= min(2.0, 0.4 * len(unavailable))
    if unavailable:
        notes.append(f"{len(unavailable)} unavailable dimension(s)")

    return _dimension(
        "risk",
        score=_clamp(score, 0.0, 10.0),
        weight=weight,
        evidence=list(items),
        rationale="; ".join(notes),
    )


def _dimension(
    name: ScoringDimension,
    *,
    score: float,
    weight: float,
    evidence: Sequence[Evidence],
    rationale: str,
) -> DimensionScore:
    unique_ids: list[str] = []
    for item in evidence:
        if item.evidence_id not in unique_ids:
            unique_ids.append(item.evidence_id)
    confidence = _mean([item.confidence for item in evidence]) if evidence else 0.0
    return DimensionScore(
        dimension=name,
        score=_quantize(score),
        weight=weight,
        supporting_evidence=unique_ids,
        confidence=_quantize(confidence, places=4),
        missing=False,
        rationale=rationale,
    )


def _missing(name: ScoringDimension, weight: float) -> DimensionScore:
    return DimensionScore(
        dimension=name,
        score=0.0,
        weight=weight,
        supporting_evidence=[],
        confidence=0.0,
        missing=True,
        rationale="no validated evidence for this dimension",
    )


def _competition_level(item: Evidence) -> float | None:
    candidates: list[Any] = [item.value]
    data = _data(item)
    candidates.append(data.get("level"))
    candidates.append(data.get("competition_level"))
    if isinstance(item.value, dict):
        candidates.append(item.value.get("level"))
    for candidate in candidates:
        if (
            isinstance(candidate, str)
            and candidate.strip().upper() in _COMPETITION_LEVELS
        ):
            return _COMPETITION_LEVELS[candidate.strip().upper()]
    return None


def _looks_commercial(item: Evidence) -> bool:
    blob = " ".join(
        [
            item.claim.lower(),
            str(item.value).lower(),
            str(_data(item)).lower(),
        ]
    )
    return any(token in blob for token in _COMMERCIAL_TOKENS)


def _has_coordinates(item: Evidence) -> bool:
    data = _data(item)
    coords = data.get("coordinates")
    if isinstance(coords, dict) and "latitude" in coords and "longitude" in coords:
        return True
    return (
        _nested_float(item, "latitude") is not None
        and _nested_float(item, "longitude") is not None
    )


def _has_address(item: Evidence) -> bool:
    data = _data(item)
    address = data.get("address") or data.get("display_name")
    return isinstance(address, str) and bool(address.strip())


def _data(item: Evidence) -> dict[str, Any]:
    value = item.value
    if isinstance(value, dict):
        inner = value.get("data")
        if isinstance(inner, dict):
            return inner
        return value
    return {}


def _nested_float(item: Evidence, key: str) -> float | None:
    data = _data(item)
    if key in data:
        parsed = _as_float(data.get(key))
        if parsed is not None:
            return parsed
    if isinstance(item.value, dict) and key in item.value:
        return _as_float(item.value.get(key))
    if item.claim.lower() == key:
        return _as_float(item.value)
    nested_coords = data.get("coordinates")
    if isinstance(nested_coords, dict) and key in nested_coords:
        return _as_float(nested_coords.get(key))
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))


def _quantize(value: float | Decimal, places: int = 2) -> float:
    quantizer = Decimal(10) ** -places
    as_decimal = value if isinstance(value, Decimal) else _decimal(float(value))
    return float(as_decimal.quantize(quantizer, rounding=ROUND_HALF_EVEN))
