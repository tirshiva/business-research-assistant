"""Structured business-analysis outputs (qualitative; no numerical scores)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

InsightKind = Literal[
    "observation",
    "opportunity",
    "risk",
    "unknown",
    "inferred",
]


class CitedStatement(BaseModel):
    """A qualitative statement that may cite supporting evidence IDs."""

    statement: str = Field(..., min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    kind: InsightKind | None = None

    @field_validator("statement")
    @classmethod
    def strip_statement(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("statement must not be empty")
        return normalized

    @field_validator("evidence_ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for item in value:
            cleaned = item.strip()
            if cleaned and cleaned not in seen:
                seen.append(cleaned)
        return seen


class AnalysisInsights(BaseModel):
    """LLM-facing analysis payload. Must not include numerical scores."""

    observations: list[CitedStatement] = Field(default_factory=list)
    opportunities: list[CitedStatement] = Field(default_factory=list)
    risks: list[CitedStatement] = Field(default_factory=list)
    unknowns: list[CitedStatement] = Field(default_factory=list)
    inferred_insights: list[CitedStatement] = Field(default_factory=list)

    @model_validator(mode="after")
    def inferred_must_cite_evidence(self) -> AnalysisInsights:
        for item in self.inferred_insights:
            if not item.evidence_ids:
                raise ValueError(
                    "inferred insights must reference supporting evidence IDs"
                )
        return self


class AnalysisResult(BaseModel):
    """Full analysis envelope combining insights and a deterministic scorecard."""

    insights: AnalysisInsights
    overall_score: float = Field(..., ge=0.0, le=10.0)
    recommendation: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    scorecard: dict = Field(default_factory=dict)

    def summary_text(self) -> str:
        """Human-readable analysis for investigation state."""
        lines = [
            f"Recommendation: {self.recommendation}",
            f"Overall score: {self.overall_score:.2f}/10",
            f"Confidence: {self.confidence:.2f}",
            "",
            "Observations:",
            *_format_statements(self.insights.observations),
            "",
            "Opportunities:",
            *_format_statements(self.insights.opportunities),
            "",
            "Risks:",
            *_format_statements(self.insights.risks),
            "",
            "Unknowns:",
            *_format_statements(self.insights.unknowns),
            "",
            "Inferred insights:",
            *_format_statements(self.insights.inferred_insights),
        ]
        return "\n".join(lines)


def _format_statements(items: list[CitedStatement]) -> list[str]:
    if not items:
        return ["- (none)"]
    formatted: list[str] = []
    for item in items:
        cites = ", ".join(item.evidence_ids) if item.evidence_ids else "no evidence"
        formatted.append(f"- {item.statement} [{cites}]")
    return formatted
