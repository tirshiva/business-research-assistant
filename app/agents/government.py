"""Government open-data research agent for India public datasets."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from app.agents.base import ResearchAgent
from app.agents.schemas import AgentFinding, AgentResult, AgentSource
from app.core.exceptions import DataUnavailableError, ExternalServiceError
from app.services.external.government_data import GovernmentDataProvider


class GovernmentDataAgentInput(BaseModel):
    """Input schema for the government data agent."""

    query: str = Field(..., min_length=1)
    location: str | None = None
    business_type: str | None = None
    limit: int = Field(default=5, ge=1, le=25)


class GovernmentDataAgent(ResearchAgent):
    """Search India government open-data catalogs for relevant metadata."""

    name: ClassVar[str] = "government_data"
    allowed_tools: ClassVar[list[str]] = [
        "government_data.search",
        "government_data.get_dataset",
    ]

    def __init__(self, provider: GovernmentDataProvider) -> None:
        self._provider = provider

    async def run(self, payload: GovernmentDataAgentInput) -> AgentResult:
        self._log_start(payload)
        search_query = _compose_query(payload)

        try:
            datasets = await self._provider.search(search_query, limit=payload.limit)
        except DataUnavailableError as exc:
            return AgentResult(
                agent="government_data",
                findings=[
                    AgentFinding(
                        title="Government data unavailable",
                        summary=exc.message,
                        data={
                            "query": search_query,
                            "provider": self._provider.name,
                            "reason": "data_unavailable",
                        },
                        confidence=0.0,
                    )
                ],
                sources=[
                    AgentSource(
                        name=self._provider.name,
                        url="https://data.gov.in/",
                        tool="government_data.search",
                        notes="Structured unavailable result — no fabricated data",
                    )
                ],
                confidence=0.0,
                status="data_unavailable",
                errors=[exc.message],
                allowed_tools=list(self.allowed_tools),
            )
        except ExternalServiceError as exc:
            return AgentResult(
                agent="government_data",
                findings=[],
                sources=[],
                confidence=0.0,
                status="failed",
                errors=[exc.message],
                allowed_tools=list(self.allowed_tools),
            )

        sources = [
            AgentSource(
                name=self._provider.name,
                url="https://data.gov.in/",
                tool="government_data.search",
            )
        ]
        findings: list[AgentFinding] = []
        for dataset in datasets:
            findings.append(
                AgentFinding(
                    title=dataset.title,
                    summary=(
                        dataset.notes[:280]
                        if dataset.notes
                        else f"Dataset metadata from {self._provider.name}"
                    ),
                    data={
                        "dataset_id": dataset.id,
                        "title": dataset.title,
                        "organization": dataset.organization,
                        "source_url": dataset.source_url,
                        "tags": dataset.tags,
                        "resources": dataset.resources,
                        "query": search_query,
                        "location": payload.location,
                        "business_type": payload.business_type,
                    },
                    confidence=0.7,
                )
            )

        return AgentResult(
            agent="government_data",
            findings=findings,
            sources=sources,
            confidence=min(0.85, 0.4 + 0.08 * len(findings)) if findings else 0.0,
            status="completed" if findings else "data_unavailable",
            errors=[],
            allowed_tools=list(self.allowed_tools),
        )


def _compose_query(payload: GovernmentDataAgentInput) -> str:
    parts = [payload.query.strip()]
    if payload.location:
        parts.append(payload.location.strip())
    if payload.business_type:
        parts.append(payload.business_type.strip())
    return " ".join(part for part in parts if part)
