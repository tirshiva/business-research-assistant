"""Deterministic query analyzer node (no LLM)."""

from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger
from app.graph.state import InvestigationState

logger = get_logger(__name__)

# Simple keyword → business type mappings for the placeholder analyzer.
_BUSINESS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bcloud\s*kitchen\b", re.IGNORECASE), "cloud_kitchen"),
    (re.compile(r"\brestaurant\b", re.IGNORECASE), "restaurant"),
    (re.compile(r"\bcafe\b|\bcafé\b", re.IGNORECASE), "cafe"),
    (re.compile(r"\bgrocery\b|\bkirana\b", re.IGNORECASE), "grocery"),
    (re.compile(r"\bcoworking\b", re.IGNORECASE), "coworking"),
    (re.compile(r"\bwarehouse\b|\bgodown\b", re.IGNORECASE), "warehouse"),
    (re.compile(r"\bretaill?\b|\bstore\b|\bshop\b", re.IGNORECASE), "retail"),
)

# Capture phrases like "Sector 62 Noida", "in Connaught Place", "near Koramangala".
_LOCATION_PATTERNS: tuple[re.Pattern[str], ...] = (
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

_TARGET_CUSTOMER_PATTERN = re.compile(
    r"\b(?:targeting|target(?:ing)?)\s+([A-Za-z][A-Za-z\s/-]{1,40}?)(?:\?|$|,|\.)",
    re.IGNORECASE,
)


async def query_analyzer(state: InvestigationState) -> dict[str, Any]:
    """Analyze the user query and populate structured investigation fields.

    Uses deterministic heuristics only. Later modules may replace this with an
    LLM-backed analyzer without changing the graph contract.
    """
    query = (state.get("user_query") or "").strip()
    iteration = int(state.get("iteration") or 0) + 1

    if not query:
        logger.warning(
            "query_analyzer received empty user_query (id=%s)",
            state.get("investigation_id"),
        )
        return {
            "validation_errors": ["user_query must not be empty"],
            "status": "failed",
            "iteration": iteration,
        }

    business_type = state.get("business_type") or _infer_business_type(query)
    location = state.get("location") or _infer_location(query)
    target_customer = state.get("target_customer") or _infer_target_customer(query)
    objective = _build_objective(query, business_type=business_type, location=location)

    logger.info(
        "Analyzed query id=%s business_type=%s location=%s",
        state.get("investigation_id"),
        business_type,
        location,
    )

    return {
        "business_type": business_type,
        "location": location,
        "target_customer": target_customer,
        "objective": objective,
        "analysis": (
            "Deterministic query analysis completed. "
            "Planner will produce the structured research plan."
        ),
        "validation_errors": [],
        "status": "query_analyzed",
        "iteration": iteration,
    }


def _infer_business_type(query: str) -> str | None:
    for pattern, label in _BUSINESS_PATTERNS:
        if pattern.search(query):
            return label
    return None


def _infer_location(query: str) -> str | None:
    for pattern in _LOCATION_PATTERNS:
        match = pattern.search(query)
        if not match:
            continue
        candidate = match.group(1).strip(" .,?!")
        if candidate:
            return candidate
    return None


def _infer_target_customer(query: str) -> str | None:
    match = _TARGET_CUSTOMER_PATTERN.search(query)
    if not match:
        return None
    return match.group(1).strip(" .,?!") or None


def _build_objective(
    query: str,
    *,
    business_type: str | None,
    location: str | None,
) -> str:
    if business_type:
        business = business_type.replace("_", " ")
    else:
        business = "the proposed business"
    place = location or "the specified location"
    return (
        f"Evaluate whether {place} is a suitable location for {business}. "
        f"Original question: {query}"
    )
