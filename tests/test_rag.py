"""Tests for document RAG parse, ingest, retrieve, and agent provenance."""

from __future__ import annotations

import pytest

from app.agents.documents import DocumentsAgent, DocumentsAgentInput
from app.db.session import create_engine, create_schema, create_session_factory
from app.rag.chunker import chunk_pages
from app.rag.corpus import public_sample_corpus
from app.rag.embeddings import HashingEmbeddingProvider
from app.rag.ingest import DocumentIngestor
from app.rag.models import SourceDocument
from app.rag.parser import parse_document
from app.rag.retriever import DocumentRetriever
from app.rag.store import PgVectorStore


def test_parser_splits_explicit_page_markers() -> None:
    document = SourceDocument(
        document_id="doc-pages",
        title="Paged sample",
        source="test",
        text=(
            "[Page 1]\nIntro paragraph.\n\n"
            "[Page 17]\nOffice catchment on page seventeen."
        ),
    )
    pages = parse_document(document)
    numbers = [page.page_number for page in pages]
    assert 1 in numbers
    assert 17 in numbers
    page_17 = next(page for page in pages if page.page_number == 17)
    assert "Office catchment" in page_17.text


def test_chunker_preserves_page_and_chunk_ids() -> None:
    document = SourceDocument(
        document_id="doc-chunk",
        title="Chunk sample",
        source="test",
        text="[Page 3]\n" + ("delivery kitchen " * 40),
    )
    chunks = chunk_pages(document, parse_document(document), chunk_size=80, overlap=20)
    assert chunks
    assert all(chunk.page_number == 3 for chunk in chunks)
    assert chunks[0].chunk_id.startswith("doc-chunk:p3:c")


@pytest.mark.asyncio
async def test_ingest_retrieve_and_agent_return_provenance() -> None:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    await create_schema(engine)
    sessions = create_session_factory(engine)
    embeddings = HashingEmbeddingProvider(dim=64)
    store = PgVectorStore(sessions)
    ingestor = DocumentIngestor(store, embeddings, chunk_size=420, overlap=80)
    await ingestor.ingest_many(public_sample_corpus())

    retriever = DocumentRetriever(store, embeddings, top_k=5)
    passages = await retriever.retrieve(
        "Sector 62 office catchment prepared-food delivery",
        location="Sector 62, Noida",
        business_type="cloud kitchen",
    )
    assert passages
    assert any(
        item.document_id == "sample-noida-economic-brief-2024" for item in passages
    )
    assert any(item.page_number == 17 for item in passages)

    agent = DocumentsAgent(retriever)
    result = await agent.run(
        DocumentsAgentInput(
            query=(
                "Is Sector 62, Noida a good location for a cloud kitchen "
                "targeting office workers?"
            ),
            location="Sector 62, Noida",
            business_type="cloud kitchen",
        )
    )
    assert result.status == "completed"
    assert result.allowed_tools == ["rag.retrieve"]
    finding = result.findings[0]
    data = finding.data
    assert data["claim"]
    assert data["source"]
    assert data["document_id"]
    assert isinstance(data["page"], int)
    await engine.dispose()
