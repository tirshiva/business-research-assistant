"""Retrieve relevant document passages for a research query."""

from __future__ import annotations

from app.rag.embeddings import EmbeddingProvider
from app.rag.models import RetrievedPassage
from app.rag.store import PgVectorStore


class DocumentRetriever:
    """Embed a query and return ranked passages with provenance."""

    def __init__(
        self,
        store: PgVectorStore,
        embeddings: EmbeddingProvider,
        *,
        top_k: int = 5,
    ) -> None:
        self._store = store
        self._embeddings = embeddings
        self._top_k = top_k

    async def retrieve(
        self,
        query: str,
        *,
        location: str | None = None,
        business_type: str | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedPassage]:
        parts = [query.strip()]
        if location:
            parts.append(location.strip())
        if business_type:
            parts.append(business_type.strip())
        text = " ".join(part for part in parts if part)
        if not text:
            return []
        vector = self._embeddings.embed(text)
        return await self._store.search(vector, limit=top_k or self._top_k)
