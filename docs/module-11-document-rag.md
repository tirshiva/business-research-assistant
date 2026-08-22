# Module 11 — Government Document RAG

Search public government and business-relevant reports and use retrieved
passages as evidence with provenance.

The MVP indexes **original public-domain sample texts** (CC0), not copyrighted
PDFs. Production ingest should only add documents you have rights to use.

## Pipeline

```text
Documents → Parser → Chunker → Metadata → Embeddings → Vector store
  → Retriever → Documents (RAG) agent
```

| Stage | Module | Notes |
|---|---|---|
| Parser | `app/rag/parser.py` | `[Page N]`, `--- page N ---`, form-feed; plain text only |
| Chunker | `app/rag/chunker.py` | Overlapping character chunks; `chunk_id` = `{document_id}:p{page}:c{seq}` |
| Embeddings | `app/rag/embeddings.py` | Deterministic hashing vectors (no external model) |
| Store | `app/rag/store.py` | PostgreSQL + pgvector; SQLite JSON + in-process cosine |
| Retriever | `app/rag/retriever.py` | Query + optional location / business type |
| Agent | `app/agents/documents.py` | Planner task `documents` |

## Storage

PostgreSQL tables `rag_documents` and `rag_chunks`. On startup the app runs
`CREATE EXTENSION IF NOT EXISTS vector`. Docker Compose uses
`pgvector/pgvector:pg16`.

Chunk metadata stored per row:

- `document_id`, `title`, `source`, `source_url`
- `publication_date`, `retrieved_at`
- `page_number`, `chunk_id`

## Retrieval output

Every important finding includes a source reference:

```json
{
  "claim": "...",
  "source": "...",
  "document_id": "...",
  "page": 17
}
```

Evidence conversion copies `document_id`, `page`, `chunk_id`, and `source`
onto evidence metadata.

## Planner integration

The local planner selects `documents` when the query mentions office workers,
government/policy terms, or document tokens (`report`, `census`, `guideline`,
and similar). `task_router` treats `documents` as an executable research agent.

## Seed corpus

If `RAG_SEED_ON_STARTUP` is true and the catalog is empty, four CC0 sample
briefs are ingested (economic, infrastructure, demographic, hygiene outline).
They are project-authored samples, not copies of official publications.
