"""Competition research agent using pluggable public business-data providers."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from app.agents.base import ResearchAgent
from app.agents.schemas import AgentFinding, AgentResult, AgentSource
from app.core.exceptions import DataUnavailableError, ExternalServiceError
from app.services.external.business_search import BusinessSearchProvider


class CompetitionAgentInput(BaseModel):
    """Input schema for the competition agent."""

    business_type: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    latitude: float
    longitude: float
    radius_km: float = Field(default=2.0, gt=0, le=50)
    limit: int = Field(default=10, ge=1, le=50)


class CompetitionAgent(ResearchAgent):
    """Find nearby competitors from public map / business-data sources."""

    name: ClassVar[str] = "competition"
    allowed_tools: ClassVar[list[str]] = [
        "business_search.search_nearby",
    ]

    def __init__(self, provider: BusinessSearchProvider) -> None:
        self._provider = provider

    async def run(self, payload: CompetitionAgentInput) -> AgentResult:
        self._log_start(payload)
        sources: list[AgentSource] = []
        findings: list[AgentFinding] = []

        try:
            listings = await self._provider.search_nearby(
                business_type=payload.business_type,
                latitude=payload.latitude,
                longitude=payload.longitude,
                radius_km=payload.radius_km,
                limit=payload.limit,
            )
        except DataUnavailableError as exc:
            return AgentResult(
                agent="competition",
                findings=[],
                sources=[
                    AgentSource(
                        name=self._provider.name,
                        tool="business_search",
                        notes="No listings returned",
                    )
                ],
                confidence=0.0,
                status="data_unavailable",
                errors=[exc.message],
                allowed_tools=list(self.allowed_tools),
            )
        except ExternalServiceError as exc:
            return AgentResult(
                agent="competition",
                findings=[],
                sources=[],
                confidence=0.0,
                status="failed",
                errors=[exc.message],
                allowed_tools=list(self.allowed_tools),
            )

        sources.append(
            AgentSource(
                name=self._provider.name,
                url="https://www.openstreetmap.org/",
                tool="business_search",
                notes=(
                    f"radius_km={payload.radius_km}; "
                    "public OpenStreetMap-derived listings only"
                ),
            )
        )

        for listing in listings:
            findings.append(
                AgentFinding(
                    title=listing.name,
                    summary=(
                        f"{listing.category or 'business'} near {payload.location}"
                        + (
                            f" (~{listing.distance_km} km)"
                            if listing.distance_km is not None
                            else ""
                        )
                    ),
                    data={
                        "business_name": listing.name,
                        "category": listing.category,
                        "location": {
                            "address": listing.address,
                            "latitude": listing.latitude,
                            "longitude": listing.longitude,
                            "query_location": payload.location,
                        },
                        "distance_km": listing.distance_km,
                        "source": listing.source,
                        "source_url": listing.source_url,
                        "metadata": listing.metadata,
                    },
                    confidence=0.8,
                )
            )

        confidence = min(0.9, 0.4 + 0.05 * len(findings)) if findings else 0.0
        return AgentResult(
            agent="competition",
            findings=findings,
            sources=sources,
            confidence=confidence,
            status="completed" if findings else "data_unavailable",
            errors=[],
            allowed_tools=list(self.allowed_tools),
        )
