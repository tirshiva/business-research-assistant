"""Tests for composing investigation queries from form fields."""

from app.api.compose import compose_research_query


def test_compose_prefers_research_question() -> None:
    text = compose_research_query(
        query="ignored",
        research_question="Is Noida viable for a cafe?",
        business_type="cafe",
        location="Noida",
    )
    assert text.startswith("Is Noida viable for a cafe?")


def test_compose_builds_question_from_structured_fields() -> None:
    text = compose_research_query(
        business_type="cloud kitchen",
        location="Sector 62, Noida",
        target_customer="office workers",
        budget="15 lakh",
    )
    assert "Sector 62, Noida" in text
    assert "cloud kitchen" in text
    assert "office workers" in text
    assert "15 lakh" in text


def test_compose_empty_without_inputs() -> None:
    assert compose_research_query() == ""
