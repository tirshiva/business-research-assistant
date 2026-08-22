"""Document RAG package."""

from app.rag.chunker import chunk_pages
from app.rag.embeddings import HashingEmbeddingProvider
from app.rag.ingest import DocumentIngestor
from app.rag.models import DocumentChunk, RetrievedPassage, SourceDocument
from app.rag.parser import parse_document
from app.rag.retriever import DocumentRetriever
from app.rag.store import PgVectorStore

__all__ = [
    "DocumentChunk",
    "DocumentIngestor",
    "DocumentRetriever",
    "HashingEmbeddingProvider",
    "PgVectorStore",
    "RetrievedPassage",
    "SourceDocument",
    "chunk_pages",
    "parse_document",
]
