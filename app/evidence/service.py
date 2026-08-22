"""Evidence submission service and agent-result conversion."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.agents.schemas import AgentResult, AgentSource
from app.core.exceptions import EvidenceValidationError
from app.core.logging import get_logger
from app.evidence.models import (
    ClaimKind,
    Evidence,
    EvidenceValidationResult,
    ReliabilityClass,
    SourceRecord,
    SourceType,
)
from app.evidence.repository import EvidenceRepository
from app.evidence.validator import EvidenceValidator

logger = get_logger(__name__)

_SOURCE_TYPE_BY_AGENT: dict[str, SourceType] = {
    "weather": "api",
    "geography": "map",
    "competition": "map",
    "government_data": "catalog",
}

_RELIABILITY_BY_AGENT: dict[str, ReliabilityClass] = {
    "weather": "high",
    "geography": "high",
    "competition": "medium",
    "government_data": "high",
}


class EvidenceService:
    """Validate and store evidence; convert agent outputs into evidence items."""

    def __init__(
        self,
        repository: EvidenceRepository,
        validator: EvidenceValidator | None = None,
    ) -> None:
        self._repository = repository
        self._validator = validator or EvidenceValidator()

    async def submit(
        self,
        evidence: Evidence,
        *,
        allow_contradictions: bool = True,
    ) -> tuple[Evidence, EvidenceValidationResult]:
        """Validate and persist a single evidence item.

        Contradictions are stored explicitly and do not cause silent overwrite.
        Structural issues (missing source/timestamp, duplicates) raise
        :class:`EvidenceValidationError`.
        """
        existing = await self._repository.list_by_investigation(
            evidence.investigation_id
        )
        validation = self._validator.validate(evidence, existing=existing)

        if not validation.is_valid:
            raise EvidenceValidationError(
                "Evidence failed validation",
                issues=[issue.model_dump() for issue in validation.errors],
            )

        if validation.contradictions:
            if not allow_contradictions:
                raise EvidenceValidationError(
                    "Contradictory evidence rejected",
                    issues=[issue.model_dump() for issue in validation.issues],
                )
            for contradiction in validation.contradictions:
                await self._repository.add_contradiction(contradiction)
                logger.warning(
                    "Recorded contradiction id=%s claim=%s",
                    contradiction.contradiction_id,
                    contradiction.claim,
                )

        stored = await self._repository.add(evidence)
        logger.info(
            "Stored evidence id=%s investigation=%s claim=%s kind=%s",
            stored.evidence_id,
            stored.investigation_id,
            stored.claim,
            stored.claim_kind,
        )
        return stored, validation

    async def submit_agent_result(
        self,
        *,
        investigation_id: str,
        result: AgentResult,
        claim_kind: ClaimKind = "FACT",
    ) -> list[Evidence]:
        """Convert an agent result into evidence items and persist them."""
        items = evidence_from_agent_result(
            investigation_id=investigation_id,
            result=result,
            claim_kind=claim_kind,
        )
        stored_items: list[Evidence] = []
        for item in items:
            stored, _validation = await self.submit(item)
            stored_items.append(stored)
        return stored_items

    async def get_claim_provenance(
        self,
        investigation_id: str,
        claim: str,
    ) -> dict[str, Any]:
        """Trace a claim back to supporting evidence and sources."""
        evidence_items = await self._repository.find_by_claim(investigation_id, claim)
        contradictions = [
            item
            for item in await self._repository.list_contradictions(investigation_id)
            if " ".join(item.claim.lower().split()) == " ".join(claim.lower().split())
        ]
        confidence = self._validator.aggregate_confidence(evidence_items)
        return {
            "investigation_id": investigation_id,
            "claim": claim,
            "evidence": [item.model_dump(mode="json") for item in evidence_items],
            "sources": [
                {
                    "name": item.source.name,
                    "source_type": item.source.source_type,
                    "url": item.source_url or item.source.url,
                    "retrieved_at": item.retrieved_at.isoformat(),
                    "reliability": item.source.reliability,
                    "evidence_id": item.evidence_id,
                }
                for item in evidence_items
            ],
            "contradictions": [item.model_dump(mode="json") for item in contradictions],
            "confidence": confidence,
        }

    async def list_investigation_evidence(
        self,
        investigation_id: str,
    ) -> list[Evidence]:
        """Return all evidence for an investigation."""
        return await self._repository.list_by_investigation(investigation_id)


def evidence_from_agent_result(
    *,
    investigation_id: str,
    result: AgentResult,
    claim_kind: ClaimKind = "FACT",
) -> list[Evidence]:
    """Map agent findings into Evidence records (no recommendations invented)."""
    if claim_kind == "RECOMMENDATION":
        # Agents must not emit recommendations as evidence of fact.
        raise ValueError(
            "Agent findings must not be submitted as RECOMMENDATION evidence"
        )

    primary_source = _select_source(result)
    source_record = _to_source_record(
        agent=result.agent,
        agent_source=primary_source,
    )
    items: list[Evidence] = []
    for finding in result.findings:
        claim = finding.title.strip() or finding.summary.strip()
        if not claim:
            continue
        confidence = (
            finding.confidence if finding.confidence is not None else result.confidence
        )
        items.append(
            Evidence(
                investigation_id=investigation_id,
                agent=result.agent,
                claim=claim,
                value={
                    "summary": finding.summary,
                    "data": finding.data,
                },
                claim_kind=claim_kind,
                source=source_record,
                source_url=source_record.url,
                retrieved_at=source_record.retrieved_at,
                confidence=confidence,
                metadata={
                    "agent_status": result.status,
                    "finding_title": finding.title,
                },
            )
        )
    return items


def build_evidence(
    *,
    investigation_id: str,
    agent: str,
    claim: str,
    value: Any,
    source_name: str,
    claim_kind: ClaimKind = "FACT",
    source_url: str | None = None,
    source_type: SourceType = "api",
    reliability: ReliabilityClass = "unknown",
    confidence: float = 0.5,
    retrieved_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> Evidence:
    """Convenience constructor for manually authored evidence."""
    timestamp = retrieved_at or datetime.now(UTC)
    return Evidence(
        investigation_id=investigation_id,
        agent=agent,
        claim=claim,
        value=value,
        claim_kind=claim_kind,
        source=SourceRecord(
            name=source_name,
            source_type=source_type,
            url=source_url,
            retrieved_at=timestamp,
            reliability=reliability,
        ),
        source_url=source_url,
        retrieved_at=timestamp,
        confidence=confidence,
        metadata=metadata or {},
    )


def _select_source(result: AgentResult) -> AgentSource | None:
    return result.sources[0] if result.sources else None


def _to_source_record(
    *,
    agent: str,
    agent_source: AgentSource | None,
) -> SourceRecord:
    if agent_source is None:
        return SourceRecord(
            name=f"{agent}-unspecified",
            source_type=_SOURCE_TYPE_BY_AGENT.get(agent, "other"),
            url=None,
            retrieved_at=datetime.now(UTC),
            reliability="unknown",
        )
    return SourceRecord(
        name=agent_source.name,
        source_type=_SOURCE_TYPE_BY_AGENT.get(agent, "api"),
        url=agent_source.url,
        retrieved_at=agent_source.retrieved_at,
        reliability=_RELIABILITY_BY_AGENT.get(agent, "unknown"),
    )
