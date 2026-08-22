"""Documents RAG research agent."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from app.agents.base import ResearchAgent
from app.agents.schemas import AgentFinding, AgentResult, AgentSource
from app.rag.retriever import DocumentRetriever


class DocumentsAgentInput(BaseModel):
    """Input schema for document RAG research."""

    query: str = Field(..., min_length=1)
    location: str | None = None
    business_type: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class DocumentsAgent(ResearchAgent):
    """Search ingested public documents and return cited passages."""

    name: ClassVar[str] = "documents"
    allowed_tools: ClassVar[list[str]] = [
        "rag.retrieve",
    ]

    def __init__(self, retriever: DocumentRetriever) -> None:
        self._retriever = retriever

    async def run(self, payload: DocumentsAgentInput) -> AgentResult:
        self._log_start(payload)
        passages = await self._retriever.retrieve(
            payload.query,
            location=payload.location,
            business_type=payload.business_type,
            top_k=payload.top_k,
        )
        if not passages:
            return AgentResult(
                agent="documents",
                findings=[],
                sources=[],
                confidence=0.0,
                status="data_unavailable",
                errors=["No relevant public document passages were retrieved"],
                allowed_tools=list(self.allowed_tools),
            )

        findings: list[AgentFinding] = []
        sources: list[AgentSource] = []
        seen_urls: set[str] = set()
        for passage in passages:
            claim = passage.text[:240]
            findings.append(
                AgentFinding(
                    title=passage.title,
                    summary=claim,
                    data={
                        "claim": claim,
                        "source": passage.source,
                        "document_id": passage.document_id,
                        "page": passage.page_number,
                        "chunk_id": passage.chunk_id,
                        "source_url": passage.source_url,
                        "publication_date": (
                            passage.publication_date.isoformat()
                            if passage.publication_date
                            else None
                        ),
                        "score": passage.score,
                    },
                    confidence=round(min(0.95, 0.45 + passage.score * 0.5), 4),
                )
            )
            key = passage.source_url or passage.document_id
            if key not in seen_urls:
                seen_urls.add(key)
                sources.append(
                    AgentSource(
                        name=passage.source,
                        url=passage.source_url,
                        tool="rag.retrieve",
                        notes=f"document_id={passage.document_id}",
                    )
                )

        confidence = round(
            sum(item.confidence or 0.0 for item in findings) / len(findings),
            4,
        )
        return AgentResult(
            agent="documents",
            findings=findings,
            sources=sources,
            confidence=confidence,
            status="completed",
            allowed_tools=list(self.allowed_tools),
        )
