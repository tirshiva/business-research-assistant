"""Tests for deterministic opportunity scoring."""

from __future__ import annotations

import pytest

from app.evidence.service import build_evidence
from app.scoring import ScoringConfig, map_score_to_recommendation, score_opportunity
from app.scoring.engine import score_opportunity as score_fn


def _evidence(
    *,
    evidence_id: str,
    agent: str,
    claim: str,
    value: object,
    confidence: float = 0.8,
) -> object:
    item = build_evidence(
        investigation_id="inv-score",
        agent=agent,
        claim=claim,
        value=value,
        source_name=f"{agent}-source",
        source_url="https://example.test/",
        confidence=confidence,
        claim_kind="FACT",
    )
    return item.model_copy(update={"evidence_id": evidence_id})


def _full_set() -> list[object]:
    return [
        _evidence(
            evidence_id="e-geo",
            agent="geography",
            claim="Resolved location",
            value={
                "summary": "Sector 62, Noida",
                "data": {
                    "coordinates": {"latitude": 28.628, "longitude": 77.365},
                    "address": "Sector 62, Noida",
                },
            },
        ),
        _evidence(
            evidence_id="e-comp",
            agent="competition",
            claim="Demo Kitchen",
            value={
                "summary": "Nearby competitor",
                "data": {"distance_km": 0.4, "business_name": "Demo Kitchen"},
            },
        ),
        _evidence(
            evidence_id="e-wx",
            agent="weather",
            claim="temperature_c",
            value={"summary": "Warm", "data": {"temperature_c": 33.0}},
        ),
        _evidence(
            evidence_id="e-gov",
            agent="government_data",
            claim="Sample Dataset",
            value={"summary": "Catalog hit", "data": {"dataset_id": "ds-1"}},
        ),
    ]


def test_same_evidence_always_produces_same_score() -> None:
    evidence = _full_set()
    first = score_opportunity(evidence)
    second = score_opportunity(list(reversed(evidence)))

    assert first.overall_score == second.overall_score
    assert first.recommendation == second.recommendation
    assert [dim.score for dim in first.dimensions] == [
        dim.score for dim in second.dimensions
    ]


def test_recommendation_is_traceable_to_dimensions_and_evidence() -> None:
    scorecard = score_opportunity(_full_set())

    assert scorecard.formula.startswith("overall = sum")
    assert scorecard.evidence_ids
    for dim in scorecard.dimensions:
        if not dim.missing:
            assert dim.supporting_evidence
            assert set(dim.supporting_evidence) <= set(scorecard.evidence_ids)
            assert 0.0 <= dim.score <= 10.0
            assert 0.0 <= dim.confidence <= 1.0
            assert dim.weight > 0
    assert scorecard.recommendation != "INSUFFICIENT DATA"


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (10.0, "STRONG OPPORTUNITY"),
        (8.5, "STRONG OPPORTUNITY"),
        (8.49, "PROMISING"),
        (7.0, "PROMISING"),
        (6.99, "PROCEED WITH CAUTION"),
        (5.0, "PROCEED WITH CAUTION"),
        (4.99, "WEAK OPPORTUNITY"),
        (3.0, "WEAK OPPORTUNITY"),
        (2.99, "LOW OPPORTUNITY"),
        (0.0, "LOW OPPORTUNITY"),
    ],
)
def test_recommendation_bands(score: float, label: str) -> None:
    assert map_score_to_recommendation(score) == label


def test_missing_critical_evidence_is_insufficient_data() -> None:
    weather_only = [
        _evidence(
            evidence_id="e-wx",
            agent="weather",
            claim="temperature_c",
            value={"summary": "Warm", "data": {"temperature_c": 33.0}},
        )
    ]
    scorecard = score_opportunity(weather_only)

    assert scorecard.recommendation == "INSUFFICIENT DATA"
    assert "demand" in scorecard.critical_missing
    assert "competition" in scorecard.critical_missing
    assert "accessibility" in scorecard.critical_missing
    assert scorecard.overall_score >= 0.0


def test_weights_are_applied_deterministically() -> None:
    evidence = _full_set()
    default = score_opportunity(evidence)
    tilted = score_opportunity(
        evidence,
        ScoringConfig(
            weights={
                "demand": 0.05,
                "competition": 0.05,
                "accessibility": 0.05,
                "infrastructure": 0.05,
                "market_indicators": 0.05,
                "risk": 0.75,
            }
        ),
    )
    assert default.overall_score != tilted.overall_score


def test_recommendation_evidence_is_not_used_as_fact() -> None:
    facts = _full_set()
    recommendation = build_evidence(
        investigation_id="inv-score",
        agent="analysis",
        claim="should open here",
        value="STRONG",
        source_name="invented",
        claim_kind="RECOMMENDATION",
        confidence=1.0,
    ).model_copy(update={"evidence_id": "e-rec"})

    with_rec = score_fn([*facts, recommendation])
    without_rec = score_fn(facts)
    assert with_rec.overall_score == without_rec.overall_score
    assert "e-rec" not in with_rec.evidence_ids
