"""Research plan models produced by the planner node."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ResearchTaskType = Literal[
    "demographics",
    "competition",
    "geography",
    "infrastructure",
    "weather",
    "government_data",
    "documents",
]

SUPPORTED_RESEARCH_TASKS: frozenset[str] = frozenset(
    {
        "demographics",
        "competition",
        "geography",
        "infrastructure",
        "weather",
        "government_data",
        "documents",
    }
)

_TASK_ALIASES: dict[str, str] = {
    "accessibility": "geography",
    "geo": "geography",
    "infra": "infrastructure",
    "govt_data": "government_data",
    "government": "government_data",
    "docs": "documents",
}

KNOWN_OBJECTIVES: frozenset[str] = frozenset(
    {
        "location evaluation",
        "market entry",
        "competition assessment",
        "site comparison",
        "general research",
    }
)

ObjectiveType = Literal[
    "location evaluation",
    "market entry",
    "competition assessment",
    "site comparison",
    "general research",
]


class ResearchPlan(BaseModel):
    """Validated structured research plan for downstream agent nodes."""

    business_type: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    objective: ObjectiveType | str = Field(..., min_length=1)
    target_customer: str | None = None
    research_tasks: list[ResearchTaskType] = Field(..., min_length=1)

    @field_validator("business_type", "location", "objective")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must not be empty")
        return normalized

    @field_validator("target_customer")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("research_tasks", mode="before")
    @classmethod
    def normalize_tasks(cls, value: object) -> list[str]:
        if not isinstance(value, list) or not value:
            raise ValueError("research_tasks must contain at least one task")
        normalized: list[str] = []
        seen: set[str] = set()
        for task in value:
            task_name = str(task).strip().lower().replace(" ", "_")
            task_name = _TASK_ALIASES.get(task_name, task_name)
            if task_name not in SUPPORTED_RESEARCH_TASKS:
                raise ValueError(f"unsupported research task: {task}")
            if task_name not in seen:
                normalized.append(task_name)
                seen.add(task_name)
        return normalized
