"""Local LLM provider (first working implementation).

Uses deterministic structured planning heuristics so the application can run
without a remote model. The same ``LLMProvider`` interface is used by Bedrock
and future OpenAI-compatible local servers.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.exceptions import LLMStructuredOutputError
from app.core.logging import get_logger
from app.llm.base import LLMProvider
from app.models.research_plan import KNOWN_OBJECTIVES, ResearchPlan, ResearchTaskType

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

_TARGET_CUSTOMER_PATTERN = re.compile(
    r"\b(?:targeting|target(?:ing)?|for|serving)\s+"
    r"([A-Za-z][A-Za-z\s/-]{1,40}?)(?:\?|$|,|\.|$)",
    re.IGNORECASE,
)


class LocalLLMProvider(LLMProvider):
    """Local structured-generation provider used as the default MVP backend."""

    name = "local"

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        del system_prompt  # Prompt is used by remote providers; local uses payload.
        logger.debug(
            "LocalLLMProvider generating structured %s",
            response_model.__name__,
        )

        if response_model is ResearchPlan:
            payload = self._plan_from_prompt(user_prompt)
        else:
            raise LLMStructuredOutputError(
                f"LocalLLMProvider does not support model {response_model.__name__}",
                provider=self.name,
            )

        try:
            return response_model.model_validate(payload)
        except ValidationError as exc:
            raise LLMStructuredOutputError(
                "Local provider produced an invalid structured payload",
                provider=self.name,
                details=str(exc),
            ) from exc

    def _plan_from_prompt(self, user_prompt: str) -> dict[str, Any]:
        """Derive a ResearchPlan payload from the planner prompt text."""
        context = self._extract_context(user_prompt)
        query = context.get("user_query") or user_prompt
        business_type = _humanize_business_type(
            str(context.get("business_type") or _infer_business_type(query) or "")
        )
        location = str(context.get("location") or _infer_location(query) or "").strip()
        target_customer = context.get("target_customer") or (
            _infer_target_customer(query)
        )
        objective = _normalize_objective(context.get("objective"), query=query)

        tasks = _select_research_tasks(
            query=query,
            business_type=business_type,
            objective=objective,
        )

        return {
            "business_type": business_type,
            "location": location,
            "objective": objective,
            "target_customer": target_customer,
            "research_tasks": tasks,
        }

    @staticmethod
    def _extract_context(user_prompt: str) -> dict[str, Any]:
        """Parse optional JSON context embedded by the planner service."""
        marker = "CONTEXT_JSON:"
        if marker not in user_prompt:
            return {}
        raw = user_prompt.split(marker, maxsplit=1)[1].strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}


def _humanize_business_type(value: str) -> str:
    return value.replace("_", " ").strip()


def _normalize_objective(raw: object, *, query: str) -> str:
    if isinstance(raw, str):
        candidate = raw.strip().lower()
        if candidate in KNOWN_OBJECTIVES:
            return candidate
    return _infer_objective(query)


def _infer_business_type(query: str) -> str | None:
    patterns: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"\bcloud\s*kitchen\b", re.I), "cloud kitchen"),
        (re.compile(r"\brestaurant\b", re.I), "restaurant"),
        (re.compile(r"\bcafe\b|\bcafé\b", re.I), "cafe"),
        (re.compile(r"\bgrocery\b|\bkirana\b", re.I), "grocery"),
        (re.compile(r"\bcoworking\b", re.I), "coworking"),
        (re.compile(r"\bwarehouse\b|\bgodown\b", re.I), "warehouse"),
        (re.compile(r"\bretaill?\b|\bstore\b|\bshop\b", re.I), "retail"),
    )
    for pattern, label in patterns:
        if pattern.search(query):
            return label
    return None


def _infer_location(query: str) -> str | None:
    patterns = (
        re.compile(
            r"\b(Sector\s+\d+[A-Za-z]?(?:\s*,\s*|\s+)"
            r"[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)",
        ),
        re.compile(
            r"\b(Sector\s+\d+[A-Za-z]?(?:\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)?)",
        ),
        re.compile(
            r"\b(?:in|at|near)\s+"
            r"([A-Z][A-Za-z0-9]*(?:\s+[A-Z0-9][A-Za-z0-9]*){0,4})",
        ),
    )
    for pattern in patterns:
        match = pattern.search(query)
        if match:
            return match.group(1).strip(" .,?!")
    return None


def _infer_target_customer(query: str) -> str | None:
    match = _TARGET_CUSTOMER_PATTERN.search(query)
    if not match:
        return None
    candidate = match.group(1).strip(" .,?!")
    # Avoid capturing the business itself ("for a cloud kitchen").
    if re.search(r"\b(cloud\s*kitchen|restaurant|cafe|store|shop)\b", candidate, re.I):
        return None
    if candidate.lower().startswith(("a ", "an ", "the ")):
        return None
    return candidate


def _infer_objective(query: str) -> str:
    lowered = query.lower()
    location_tokens = ("good location", "suitable", "site", "where")
    if any(token in lowered for token in location_tokens):
        return "location evaluation"
    if "compet" in lowered:
        return "competition assessment"
    if "enter" in lowered or "launch" in lowered:
        return "market entry"
    if "compare" in lowered:
        return "site comparison"
    return "general research"


def _select_research_tasks(
    *,
    query: str,
    business_type: str,
    objective: str,
) -> list[ResearchTaskType]:
    """Select only task types relevant to the question (dynamic planning)."""
    lowered = query.lower()
    business = business_type.lower()
    tasks: list[ResearchTaskType] = []

    def add(task: ResearchTaskType) -> None:
        if task not in tasks:
            tasks.append(task)

    # Core tasks for location / market questions.
    if objective in {"location evaluation", "market entry", "site comparison"}:
        add("demographics")
        add("competition")
        add("geography")
        add("infrastructure")

    if "compet" in lowered or objective == "competition assessment":
        add("competition")

    demographic_tokens = ("demographic", "population", "office worker")
    if any(token in lowered for token in demographic_tokens):
        add("demographics")

    access_tokens = ("road", "metro", "access", "parking", "infra")
    if any(token in lowered for token in access_tokens):
        add("infrastructure")
        add("geography")

    # Weather only when clearly relevant (delivery exposure or explicit ask).
    weather_sensitive = any(
        token in business
        for token in ("cloud kitchen", "restaurant", "cafe", "food", "outdoor")
    )
    weather_tokens = ("weather", "rain", "monsoon", "climate", "heat")
    weather_asked = any(token in lowered for token in weather_tokens)
    logistics_weather = (
        weather_asked or "cloud kitchen" in business or "delivery" in lowered
    )
    location_eval = objective == "location evaluation" and "indoor only" not in lowered
    if logistics_weather and (weather_asked or (weather_sensitive and location_eval)):
        add("weather")

    gov_tokens = (
        "license",
        "fssai",
        "permit",
        "zoning",
        "gst",
        "government",
        "policy",
    )
    if any(token in lowered for token in gov_tokens):
        add("government_data")
        add("documents")

    document_tokens = ("document", "report", "guideline", "regulation")
    if any(token in lowered for token in document_tokens):
        add("documents")

    # Ambiguous / underspecified questions get a minimal safe set.
    if not tasks:
        add("demographics")
        add("competition")

    return tasks
