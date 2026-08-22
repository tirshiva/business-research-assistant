"""Compose a research query from structured investigation form fields."""

from __future__ import annotations


def compose_research_query(
    *,
    query: str | None = None,
    research_question: str | None = None,
    business_type: str | None = None,
    location: str | None = None,
    target_customer: str | None = None,
    budget: str | None = None,
) -> str:
    """Build the natural-language question sent to the investigation graph.

    Prefers ``research_question``, then ``query``. Structured fields are appended
    when they are not already present in the question text.
    """
    question = (research_question or query or "").strip()
    business = (business_type or "").strip()
    place = (location or "").strip()
    customer = (target_customer or "").strip()
    budget_text = (budget or "").strip()

    if not question:
        if business and place:
            question = f"Is {place} a good location for a {business}?"
        elif business:
            question = f"Evaluate the opportunity for a {business}."
        elif place:
            question = f"Evaluate business opportunity in {place}."

    extras: list[str] = []
    lowered = question.lower()
    if business and business.lower() not in lowered:
        extras.append(f"Business type: {business}.")
    if place and place.lower() not in lowered:
        extras.append(f"Location: {place}.")
    if customer and customer.lower() not in lowered:
        extras.append(f"Target customer: {customer}.")
    if budget_text:
        extras.append(f"Budget: {budget_text}.")

    assembled = " ".join(part for part in [question, *extras] if part).strip()
    return assembled
