"""Vector store for document chunks (PostgreSQL + pgvector, SQLite fallback)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.rag.embeddings import cosine_similarity
from app.rag.models import DocumentChunk, RetrievedPassage
from app.rag.tables import RagChunkRow, RagDocumentRow


class PgVectorStore:
    """Persist chunks and run similarity search.

    PostgreSQL uses pgvector (``<=>``). SQLite (tests) uses in-process cosine
    over JSON embeddings.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def upsert_document(
        self,
        *,
        document_id: str,
        title: str,
        source: str,
        source_url: str | None,
        publication_date,
        retrieved_at,
        category: str,
        license_name: str,
    ) -> None:
        async with self._sessions() as session:
            existing = await session.get(RagDocumentRow, document_id)
            if existing is None:
                session.add(
                    RagDocumentRow(
                        document_id=document_id,
                        title=title,
                        source=source,
                        source_url=source_url,
                        publication_date=publication_date,
                        retrieved_at=retrieved_at,
                        category=category,
                        license=license_name,
                    )
                )
            else:
                existing.title = title
                existing.source = source
                existing.source_url = source_url
                existing.publication_date = publication_date
                existing.retrieved_at = retrieved_at
                existing.category = category
                existing.license = license_name
            await session.commit()

    async def replace_chunks(
        self,
        document_id: str,
        chunks: Sequence[DocumentChunk],
    ) -> None:
        async with self._sessions() as session:
            await session.execute(
                delete(RagChunkRow).where(RagChunkRow.document_id == document_id)
            )
            for chunk in chunks:
                session.add(_chunk_to_row(chunk))
            await session.commit()

    async def document_count(self) -> int:
        async with self._sessions() as session:
            result = await session.scalars(select(RagDocumentRow.document_id))
            return len(list(result.all()))

    async def search(
        self,
        embedding: list[float],
        *,
        limit: int = 5,
    ) -> list[RetrievedPassage]:
        async with self._sessions() as session:
            dialect = (
                session.bind.dialect.name if session.bind is not None else "sqlite"
            )
            if dialect == "postgresql":
                hits = await _pgvector_search(session, embedding, limit=limit)
                if hits:
                    return hits
            result = await session.scalars(select(RagChunkRow))
            rows = list(result.all())
        scored = [
            _row_to_passage(
                row,
                cosine_similarity(embedding, list(row.embedding)),
            )
            for row in rows
            if row.embedding
        ]
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[: max(1, limit)]


async def _pgvector_search(
    session: AsyncSession,
    embedding: list[float],
    *,
    limit: int,
) -> list[RetrievedPassage]:
    try:
        result = await session.execute(
            text(
                """
                SELECT chunk_id, document_id, title, source, source_url,
                       publication_date, retrieved_at, page_number, content,
                       1 - (embedding <=> :query) AS score
                FROM rag_chunks
                ORDER BY embedding <=> :query
                LIMIT :limit
                """
            ),
            {"query": str(embedding), "limit": limit},
        )
    except Exception:  # noqa: BLE001
        return []
    passages: list[RetrievedPassage] = []
    for row in result.mappings():
        raw_score = float(row["score"] or 0.0)
        passages.append(
            RetrievedPassage(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                title=row["title"],
                source=row["source"],
                source_url=row["source_url"],
                publication_date=row["publication_date"],
                retrieved_at=row["retrieved_at"],
                page_number=int(row["page_number"]),
                text=row["content"],
                score=max(0.0, min(1.0, raw_score)),
            )
        )
    return passages


def _chunk_to_row(chunk: DocumentChunk) -> RagChunkRow:
    return RagChunkRow(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        title=chunk.title,
        source=chunk.source,
        source_url=chunk.source_url,
        publication_date=chunk.publication_date,
        retrieved_at=chunk.retrieved_at,
        page_number=chunk.page_number,
        content=chunk.text,
        embedding=list(chunk.embedding),
    )


def _row_to_passage(row: RagChunkRow, score: float) -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        title=row.title,
        source=row.source,
        source_url=row.source_url,
        publication_date=row.publication_date,
        retrieved_at=row.retrieved_at,
        page_number=row.page_number,
        text=row.content,
        score=score,
    )
