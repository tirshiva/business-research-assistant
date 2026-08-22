"""Ingest pipeline: parse → chunk → embed → vector store."""

from __future__ import annotations

from app.core.logging import get_logger
from app.rag.chunker import chunk_pages
from app.rag.embeddings import EmbeddingProvider
from app.rag.models import SourceDocument
from app.rag.parser import parse_document
from app.rag.store import PgVectorStore

logger = get_logger(__name__)


class DocumentIngestor:
    """Run the RAG ingest pipeline for public documents."""

    def __init__(
        self,
        store: PgVectorStore,
        embeddings: EmbeddingProvider,
        *,
        chunk_size: int = 420,
        overlap: int = 80,
    ) -> None:
        self._store = store
        self._embeddings = embeddings
        self._chunk_size = chunk_size
        self._overlap = overlap

    async def ingest(self, document: SourceDocument) -> int:
        """Index one document and return the number of chunks stored."""
        pages = parse_document(document)
        chunks = chunk_pages(
            document,
            pages,
            chunk_size=self._chunk_size,
            overlap=self._overlap,
        )
        if not chunks:
            logger.warning(
                "No chunks produced for document_id=%s",
                document.document_id,
            )
            return 0
        vectors = self._embeddings.embed_many([chunk.text for chunk in chunks])
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk.embedding = vector
        await self._store.upsert_document(
            document_id=document.document_id,
            title=document.title,
            source=document.source,
            source_url=document.source_url,
            publication_date=document.publication_date,
            retrieved_at=document.retrieved_at,
            category=document.category,
            license_name=document.license,
        )
        await self._store.replace_chunks(document.document_id, chunks)
        logger.info(
            "Ingested document_id=%s chunks=%s",
            document.document_id,
            len(chunks),
        )
        return len(chunks)

    async def ingest_many(self, documents: list[SourceDocument]) -> int:
        total = 0
        for document in documents:
            total += await self.ingest(document)
        return total
