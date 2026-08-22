"""Critic verdict models for the self-correction loop."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

CriticStatus = Literal["PASS", "FAIL"]
CriticCheck = Literal[
    "evidence_coverage",
    "source_quality",
    "data_freshness",
    "contradictions",
    "unsupported_claims",
    "logical_consistency",
    "missing_critical_information",
]


class CriticIssue(BaseModel):
    """A single quality-control finding."""

    check: CriticCheck
    message: str = Field(..., min_length=1)
    severity: Literal["error", "warning"] = "error"
    research_task: str | None = None

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("issue message must not be empty")
        return normalized


class CriticVerdict(BaseModel):
    """PASS/FAIL evaluation of an investigation before the final report."""

    status: CriticStatus
    confidence: float = Field(..., ge=0.0, le=1.0)
    issues: list[CriticIssue] = Field(default_factory=list)
    required_research: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, value: float) -> float:
        return round(float(value), 4)

    @field_validator("required_research")
    @classmethod
    def unique_tasks(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for item in value:
            task = item.strip().lower()
            if task and task not in seen:
                seen.append(task)
        return seen

    def public_dict(self) -> dict[str, object]:
        """Wire-format payload matching the module contract."""
        return {
            "status": self.status,
            "confidence": self.confidence,
            "issues": [issue.message for issue in self.issues],
            "required_research": list(self.required_research),
        }
