"""Domain models for the document RAG pipeline."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

DocumentCategory = Literal[
    "government_report",
    "economic_report",
    "infrastructure_report",
    "demographic_report",
    "business_report",
]


class SourceDocument(BaseModel):
    """A public document eligible for ingestion."""

    document_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    source_url: str | None = None
    publication_date: date | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    category: DocumentCategory = "government_report"
    license: str = "CC0-1.0"
    text: str = Field(..., min_length=1)

    @field_validator("document_id", "title", "source", "text")
    @classmethod
    def strip_required(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must not be empty")
        return normalized


class ParsedPage(BaseModel):
    """Plain text extracted from a single document page."""

    page_number: int = Field(..., ge=1)
    text: str


class DocumentChunk(BaseModel):
    """Embedded passage stored in the vector index."""

    chunk_id: str = Field(..., min_length=1)
    document_id: str = Field(..., min_length=1)
    title: str
    source: str
    source_url: str | None = None
    publication_date: date | None = None
    retrieved_at: datetime
    page_number: int = Field(..., ge=1)
    text: str = Field(..., min_length=1)
    embedding: list[float] = Field(default_factory=list)


class RetrievedPassage(BaseModel):
    """Retriever hit with provenance for the RAG agent."""

    chunk_id: str
    document_id: str
    title: str
    source: str
    source_url: str | None = None
    publication_date: date | None = None
    retrieved_at: datetime
    page_number: int
    text: str
    score: float = Field(..., ge=0.0, le=1.0)
