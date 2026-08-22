"""Chunker — split parsed pages into overlapping passages."""

from __future__ import annotations

from collections.abc import Sequence

from app.rag.models import DocumentChunk, ParsedPage, SourceDocument


def chunk_pages(
    document: SourceDocument,
    pages: Sequence[ParsedPage],
    *,
    chunk_size: int = 420,
    overlap: int = 80,
) -> list[DocumentChunk]:
    """Create overlapping character chunks, preserving page numbers."""
    size = max(80, chunk_size)
    step_overlap = max(0, min(overlap, size - 1))
    chunks: list[DocumentChunk] = []
    sequence = 0
    for page in pages:
        text = " ".join(page.text.split())
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            piece = text[start:end].strip()
            if piece:
                sequence += 1
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{document.document_id}:p{page.page_number}:c{sequence}",
                        document_id=document.document_id,
                        title=document.title,
                        source=document.source,
                        source_url=document.source_url,
                        publication_date=document.publication_date,
                        retrieved_at=document.retrieved_at,
                        page_number=page.page_number,
                        text=piece,
                    )
                )
            if end >= len(text):
                break
            start = end - step_overlap
    return chunks
