"""Configurable opportunity-scoring models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ScoringDimension = Literal[
    "demand",
    "competition",
    "accessibility",
    "infrastructure",
    "market_indicators",
    "risk",
]

SCORING_DIMENSIONS: tuple[ScoringDimension, ...] = (
    "demand",
    "competition",
    "accessibility",
    "infrastructure",
    "market_indicators",
    "risk",
)

Recommendation = Literal[
    "STRONG OPPORTUNITY",
    "PROMISING",
    "PROCEED WITH CAUTION",
    "WEAK OPPORTUNITY",
    "LOW OPPORTUNITY",
    "INSUFFICIENT DATA",
]

DEFAULT_WEIGHTS: dict[ScoringDimension, float] = {
    "demand": 0.25,
    "competition": 0.20,
    "accessibility": 0.15,
    "infrastructure": 0.15,
    "market_indicators": 0.15,
    "risk": 0.10,
}

DEFAULT_CRITICAL_DIMENSIONS: tuple[ScoringDimension, ...] = (
    "demand",
    "competition",
    "accessibility",
)


class DimensionScore(BaseModel):
    """Score for a single configurable dimension."""

    dimension: ScoringDimension
    score: float = Field(..., ge=0.0, le=10.0)
    weight: float = Field(..., ge=0.0)
    supporting_evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    missing: bool = False
    rationale: str = ""

    @field_validator("score", "weight", "confidence")
    @classmethod
    def round_metric(cls, value: float) -> float:
        return round(float(value), 4)


class ScoringConfig(BaseModel):
    """Weights and policy for deterministic opportunity scoring."""

    weights: dict[ScoringDimension, float] = Field(
        default_factory=lambda: dict(DEFAULT_WEIGHTS)
    )
    critical_dimensions: tuple[ScoringDimension, ...] = DEFAULT_CRITICAL_DIMENSIONS

    @model_validator(mode="after")
    def validate_weights(self) -> ScoringConfig:
        missing = [name for name in SCORING_DIMENSIONS if name not in self.weights]
        if missing:
            raise ValueError(f"missing scoring weights: {missing}")
        if any(value < 0 for value in self.weights.values()):
            raise ValueError("scoring weights must be non-negative")
        if sum(self.weights.values()) <= 0:
            raise ValueError("at least one scoring weight must be positive")
        return self

    def normalized_weights(self) -> dict[ScoringDimension, float]:
        """Return weights that sum to 1.0."""
        total = sum(self.weights.values())
        return {name: value / total for name, value in self.weights.items()}


class Scorecard(BaseModel):
    """Traceable, deterministically computed opportunity score."""

    dimensions: list[DimensionScore]
    overall_score: float = Field(..., ge=0.0, le=10.0)
    recommendation: Recommendation
    weight_sum_used: float = Field(..., ge=0.0)
    formula: str
    missing_dimensions: list[ScoringDimension] = Field(default_factory=list)
    critical_missing: list[ScoringDimension] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("overall_score", "weight_sum_used")
    @classmethod
    def round_totals(cls, value: float) -> float:
        return round(float(value), 4)

    def dimension_map(self) -> dict[ScoringDimension, DimensionScore]:
        return {item.dimension: item for item in self.dimensions}
