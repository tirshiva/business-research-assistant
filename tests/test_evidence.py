"""Tests for the evidence and provenance system."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.agents.schemas import AgentFinding, AgentResult, AgentSource
from app.core.exceptions import EvidenceValidationError
from app.evidence import (
    Evidence,
    EvidenceService,
    EvidenceValidator,
    InMemoryEvidenceRepository,
    SourceRecord,
    build_evidence,
)


@pytest.fixture
def repository() -> InMemoryEvidenceRepository:
    return InMemoryEvidenceRepository()


@pytest.fixture
def service(repository: InMemoryEvidenceRepository) -> EvidenceService:
    validator = EvidenceValidator(min_confidence=0.3, stale_after_hours=24)
    return EvidenceService(repository, validator)


def _fact(
    *,
    investigation_id: str = "inv-1",
    claim: str = "competition.level",
    value: object = "LOW",
    confidence: float = 0.8,
    source_name: str = "OpenStreetMap",
    agent: str = "competition",
) -> Evidence:
    return build_evidence(
        investigation_id=investigation_id,
        agent=agent,
        claim=claim,
        value=value,
        source_name=source_name,
        source_url="https://www.openstreetmap.org/",
        source_type="map",
        reliability="medium",
        confidence=confidence,
        claim_kind="FACT",
    )


@pytest.mark.asyncio
async def test_valid_evidence_is_stored(service: EvidenceService) -> None:
    evidence = _fact()
    stored, validation = await service.submit(evidence)

    assert validation.is_valid
    assert stored.evidence_id
    assert stored.claim_kind == "FACT"
    assert stored.source.name == "OpenStreetMap"

    loaded = await service.list_investigation_evidence("inv-1")
    assert len(loaded) == 1
    assert loaded[0].evidence_id == stored.evidence_id


@pytest.mark.asyncio
async def test_missing_source_is_rejected(service: EvidenceService) -> None:
    evidence = Evidence.model_construct(
        evidence_id="e-missing-source",
        investigation_id="inv-1",
        agent="weather",
        claim="temperature_c",
        value=34.5,
        claim_kind="FACT",
        source=SourceRecord.model_construct(
            name="",
            source_type="api",
            url=None,
            retrieved_at=datetime.now(UTC),
            reliability="unknown",
        ),
        source_url=None,
        retrieved_at=datetime.now(UTC),
        confidence=0.9,
        metadata={},
    )

    with pytest.raises(EvidenceValidationError) as exc_info:
        await service.submit(evidence)

    assert any(issue["code"] == "missing_source" for issue in exc_info.value.issues)


@pytest.mark.asyncio
async def test_duplicate_evidence_is_rejected(
    service: EvidenceService,
    repository: InMemoryEvidenceRepository,
) -> None:
    first = _fact(value="LOW")
    await service.submit(first)

    duplicate = _fact(value="LOW")
    with pytest.raises(EvidenceValidationError) as exc_info:
        await service.submit(duplicate)

    assert any(issue["code"] == "duplicate_evidence" for issue in exc_info.value.issues)
    assert len(await repository.list_by_investigation("inv-1")) == 1


@pytest.mark.asyncio
async def test_conflicting_claims_create_contradiction(
    service: EvidenceService,
    repository: InMemoryEvidenceRepository,
) -> None:
    await service.submit(_fact(value="LOW", source_name="Provider A"))
    stored_b, validation = await service.submit(
        _fact(value="HIGH", source_name="Provider B")
    )

    assert validation.is_valid  # contradiction recorded, not silently dropped
    assert validation.contradictions
    assert "LOW" in str(validation.contradictions[0].values)
    assert "HIGH" in str(validation.contradictions[0].values)

    contradictions = await repository.list_contradictions("inv-1")
    assert len(contradictions) == 1
    assert stored_b.evidence_id in contradictions[0].evidence_ids
    assert len(await repository.list_by_investigation("inv-1")) == 2


def test_confidence_calculation() -> None:
    validator = EvidenceValidator()
    items = [
        build_evidence(
            investigation_id="inv-1",
            agent="weather",
            claim="temperature_c",
            value=30,
            source_name="Open-Meteo",
            reliability="high",
            confidence=0.9,
            claim_kind="FACT",
        ),
        build_evidence(
            investigation_id="inv-1",
            agent="weather",
            claim="temperature_c",
            value=31,
            source_name="Estimate",
            reliability="low",
            confidence=0.5,
            claim_kind="INFERENCE",
        ),
        build_evidence(
            investigation_id="inv-1",
            agent="planner",
            claim="should_open",
            value=True,
            source_name="n/a",
            confidence=0.99,
            claim_kind="RECOMMENDATION",
        ),
    ]

    score = validator.aggregate_confidence(items)
    assert 0.0 < score < 1.0
    # RECOMMENDATION must not dominate factual confidence.
    assert score < 0.99


@pytest.mark.asyncio
async def test_evidence_retrieval_and_provenance(service: EvidenceService) -> None:
    await service.submit(_fact(claim="competition.level", value="LOW"))
    await service.submit(
        build_evidence(
            investigation_id="inv-1",
            agent="competition",
            claim="competition.count",
            value=12,
            source_name="Overpass",
            source_url="https://overpass-api.de/",
            confidence=0.75,
        )
    )

    items = await service.list_investigation_evidence("inv-1")
    assert len(items) == 2

    provenance = await service.get_claim_provenance("inv-1", "competition.level")
    assert provenance["claim"] == "competition.level"
    assert len(provenance["evidence"]) == 1
    assert provenance["sources"][0]["name"] == "OpenStreetMap"
    assert provenance["confidence"] > 0


@pytest.mark.asyncio
async def test_stale_and_low_confidence_warnings() -> None:
    validator = EvidenceValidator(min_confidence=0.4, stale_after_hours=1)
    stale = build_evidence(
        investigation_id="inv-1",
        agent="weather",
        claim="humidity",
        value=40,
        source_name="Open-Meteo",
        confidence=0.2,
        retrieved_at=datetime.now(UTC) - timedelta(hours=5),
    )
    result = validator.validate(stale)
    codes = {issue.code for issue in result.issues}
    assert "low_confidence" in codes
    assert "stale_data" in codes
    assert result.is_valid  # warnings only by default


@pytest.mark.asyncio
async def test_submit_agent_result_as_fact_evidence(service: EvidenceService) -> None:
    agent_result = AgentResult(
        agent="weather",
        findings=[
            AgentFinding(
                title="temperature_c",
                summary="Current temperature",
                data={"temperature_c": 34.5},
                confidence=0.9,
            )
        ],
        sources=[
            AgentSource(
                name="Open-Meteo",
                url="https://open-meteo.com/",
            )
        ],
        confidence=0.9,
        status="completed",
    )

    stored = await service.submit_agent_result(
        investigation_id="inv-42",
        result=agent_result,
        claim_kind="FACT",
    )
    assert len(stored) == 1
    assert stored[0].claim_kind == "FACT"
    assert stored[0].source.name == "Open-Meteo"

    provenance = await service.get_claim_provenance("inv-42", "temperature_c")
    assert provenance["sources"][0]["url"] == "https://open-meteo.com/"


def test_claim_kinds_are_distinct() -> None:
    fact = _fact(claim="competition.level", value="LOW")
    inference = build_evidence(
        investigation_id="inv-1",
        agent="competition",
        claim="competition.level",
        value="likely moderate",
        source_name="Analyst heuristic",
        claim_kind="INFERENCE",
        confidence=0.55,
    )
    assert fact.claim_kind == "FACT"
    assert inference.claim_kind == "INFERENCE"
    assert fact.claim_kind != "RECOMMENDATION"
