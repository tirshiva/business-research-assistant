"""Evidence and provenance domain models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ClaimKind = Literal["FACT", "INFERENCE", "RECOMMENDATION"]
SourceType = Literal["api", "dataset", "document", "map", "catalog", "other"]
ReliabilityClass = Literal["high", "medium", "low", "unknown"]


class SourceRecord(BaseModel):
    """Provenance descriptor for where an evidence value came from."""

    name: str = Field(..., min_length=1)
    source_type: SourceType = "api"
    url: str | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reliability: ReliabilityClass = "unknown"

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source name must not be empty")
        return normalized


class Evidence(BaseModel):
    """Standardized evidence item produced by a research agent."""

    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = Field(..., min_length=1)
    agent: str = Field(..., min_length=1)
    claim: str = Field(..., min_length=1)
    value: Any
    claim_kind: ClaimKind = "FACT"
    source: SourceRecord
    source_url: str | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: float = Field(..., ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("claim", "agent", "investigation_id")
    @classmethod
    def strip_required(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must not be empty")
        return normalized

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, value: float) -> float:
        return round(float(value), 4)

    @property
    def normalized_claim(self) -> str:
        """Canonical claim key used for duplicate / contradiction checks."""
        return " ".join(self.claim.lower().split())


class Contradiction(BaseModel):
    """Explicit conflict between evidence items for the same claim."""

    contradiction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    claim: str
    evidence_ids: list[str] = Field(..., min_length=2)
    values: list[Any] = Field(..., min_length=2)
    summary: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationIssue(BaseModel):
    """A single evidence validation finding."""

    code: Literal[
        "missing_source",
        "missing_timestamp",
        "low_confidence",
        "duplicate_evidence",
        "contradictory_evidence",
        "stale_data",
        "invalid_claim_kind",
    ]
    message: str
    severity: Literal["error", "warning"] = "error"
    evidence_id: str | None = None


class EvidenceValidationResult(BaseModel):
    """Outcome of validating one or more evidence items."""

    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]
