"""Evidence and provenance package."""

from app.evidence.models import (
    ClaimKind,
    Contradiction,
    Evidence,
    EvidenceValidationResult,
    ReliabilityClass,
    SourceRecord,
    SourceType,
    ValidationIssue,
)
from app.evidence.repository import EvidenceRepository, InMemoryEvidenceRepository
from app.evidence.service import (
    EvidenceService,
    build_evidence,
    evidence_from_agent_result,
)
from app.evidence.validator import EvidenceValidator

__all__ = [
    "ClaimKind",
    "Contradiction",
    "Evidence",
    "EvidenceRepository",
    "EvidenceService",
    "EvidenceValidationResult",
    "EvidenceValidator",
    "InMemoryEvidenceRepository",
    "ReliabilityClass",
    "SourceRecord",
    "SourceType",
    "ValidationIssue",
    "build_evidence",
    "evidence_from_agent_result",
]
