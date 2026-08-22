"""Dependencies injected into the multi-agent investigation graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

from app.agents.schemas import AgentFinding, AgentResult, AgentSource
from app.evidence import EvidenceService, EvidenceValidator, InMemoryEvidenceRepository

if TYPE_CHECKING:
    from app.agents.competition import CompetitionAgent
    from app.agents.documents import DocumentsAgent
    from app.agents.geography import GeographyAgent
    from app.agents.government import GovernmentDataAgent
    from app.agents.weather import WeatherAgent
    from app.services.external.nominatim import NominatimClient


@dataclass
class ResearchOrchestrationDeps:
    """Agents and services required by the research orchestration graph."""

    weather_agent: WeatherAgent
    geography_agent: GeographyAgent
    competition_agent: CompetitionAgent
    government_data_agent: GovernmentDataAgent
    documents_agent: DocumentsAgent
    evidence_service: EvidenceService
    nominatim: NominatimClient | None = None
    progress_sink: Any = None

    def get_agent(self, name: str) -> Any:
        mapping = {
            "weather": self.weather_agent,
            "geography": self.geography_agent,
            "competition": self.competition_agent,
            "government_data": self.government_data_agent,
            "documents": self.documents_agent,
        }
        try:
            return mapping[name]
        except KeyError as exc:
            raise KeyError(f"No agent registered for '{name}'") from exc

    @classmethod
    def mock(
        cls,
        *,
        with_failures: set[str] | None = None,
    ) -> ResearchOrchestrationDeps:
        """Build orchestration deps with mocked agents for unit tests."""
        failures = with_failures or set()
        evidence_service = EvidenceService(
            InMemoryEvidenceRepository(),
            EvidenceValidator(),
        )

        async def _weather_run(payload: Any) -> AgentResult:
            if "weather" in failures:
                return AgentResult(
                    agent="weather",
                    findings=[],
                    sources=[],
                    confidence=0.0,
                    status="failed",
                    errors=["mocked weather failure"],
                    allowed_tools=["open_meteo.get_forecast"],
                )
            return AgentResult(
                agent="weather",
                findings=[
                    AgentFinding(
                        title="temperature_c",
                        summary="Mock temperature",
                        data={"temperature_c": 33.0},
                        confidence=0.9,
                    )
                ],
                sources=[AgentSource(name="Open-Meteo", url="https://open-meteo.com/")],
                confidence=0.9,
                status="completed",
                allowed_tools=["open_meteo.get_forecast"],
            )

        async def _geography_run(payload: Any) -> AgentResult:
            if "geography" in failures:
                return AgentResult(
                    agent="geography",
                    findings=[],
                    sources=[],
                    confidence=0.0,
                    status="data_unavailable",
                    errors=["mocked geography unavailable"],
                    allowed_tools=["nominatim.geocode"],
                )
            return AgentResult(
                agent="geography",
                findings=[
                    AgentFinding(
                        title="Resolved location",
                        summary="Sector 62, Noida",
                        data={
                            "coordinates": {
                                "latitude": 28.628,
                                "longitude": 77.365,
                            },
                            "address": "Sector 62, Noida",
                        },
                        confidence=0.9,
                    )
                ],
                sources=[
                    AgentSource(
                        name="Nominatim",
                        url="https://nominatim.openstreetmap.org/",
                    )
                ],
                confidence=0.9,
                status="completed",
                allowed_tools=["nominatim.geocode"],
            )

        async def _competition_run(payload: Any) -> AgentResult:
            if "competition" in failures:
                return AgentResult(
                    agent="competition",
                    findings=[],
                    sources=[],
                    confidence=0.0,
                    status="failed",
                    errors=["mocked competition failure"],
                    allowed_tools=["business_search.search_nearby"],
                )
            return AgentResult(
                agent="competition",
                findings=[
                    AgentFinding(
                        title="Demo Kitchen",
                        summary="Nearby competitor",
                        data={
                            "business_name": "Demo Kitchen",
                            "category": "restaurant",
                            "distance_km": 0.4,
                            "source": "overpass",
                        },
                        confidence=0.8,
                    )
                ],
                sources=[AgentSource(name="overpass")],
                confidence=0.8,
                status="completed",
                allowed_tools=["business_search.search_nearby"],
            )

        async def _government_run(payload: Any) -> AgentResult:
            if "government_data" in failures:
                return AgentResult(
                    agent="government_data",
                    findings=[],
                    sources=[],
                    confidence=0.0,
                    status="data_unavailable",
                    errors=["mocked government data unavailable"],
                    allowed_tools=["government_data.search"],
                )
            return AgentResult(
                agent="government_data",
                findings=[
                    AgentFinding(
                        title="Sample Dataset",
                        summary="Mock catalog hit",
                        data={"dataset_id": "ds-1"},
                        confidence=0.7,
                    )
                ],
                sources=[AgentSource(name="data.gov.in")],
                confidence=0.7,
                status="completed",
                allowed_tools=["government_data.search"],
            )

        async def _documents_run(payload: Any) -> AgentResult:
            if "documents" in failures:
                return AgentResult(
                    agent="documents",
                    findings=[],
                    sources=[],
                    confidence=0.0,
                    status="failed",
                    errors=["mocked documents failure"],
                    allowed_tools=["rag.retrieve"],
                )
            return AgentResult(
                agent="documents",
                findings=[
                    AgentFinding(
                        title=("NCR Food Services and Office Catchment Brief (sample)"),
                        summary=(
                            "Sector 62 office catchment supports prepared-food "
                            "delivery."
                        ),
                        data={
                            "claim": (
                                "Sector 62 office catchment supports "
                                "prepared-food delivery."
                            ),
                            "source": "India Business Research sample public corpus",
                            "document_id": "sample-noida-economic-brief-2024",
                            "page": 17,
                            "chunk_id": "sample-noida-economic-brief-2024:p17:c1",
                            "source_url": "https://data.gov.in/",
                        },
                        confidence=0.85,
                    )
                ],
                sources=[
                    AgentSource(
                        name="India Business Research sample public corpus",
                        url="https://data.gov.in/",
                    )
                ],
                confidence=0.85,
                status="completed",
                allowed_tools=["rag.retrieve"],
            )

        weather = AsyncMock()
        weather.name = "weather"
        weather.allowed_tools = ["open_meteo.get_forecast"]
        weather.run = AsyncMock(side_effect=_weather_run)

        geography = AsyncMock()
        geography.name = "geography"
        geography.allowed_tools = ["nominatim.geocode"]
        geography.run = AsyncMock(side_effect=_geography_run)

        competition = AsyncMock()
        competition.name = "competition"
        competition.allowed_tools = ["business_search.search_nearby"]
        competition.run = AsyncMock(side_effect=_competition_run)

        government = AsyncMock()
        government.name = "government_data"
        government.allowed_tools = ["government_data.search"]
        government.run = AsyncMock(side_effect=_government_run)

        documents = AsyncMock()
        documents.name = "documents"
        documents.allowed_tools = ["rag.retrieve"]
        documents.run = AsyncMock(side_effect=_documents_run)

        from app.models.location import LocationData

        nominatim = AsyncMock()
        nominatim.geocode = AsyncMock(
            return_value=LocationData(
                latitude=28.628,
                longitude=77.365,
                display_name="Sector 62, Noida, Uttar Pradesh, India",
            )
        )

        return cls(
            weather_agent=weather,
            geography_agent=geography,
            competition_agent=competition,
            government_data_agent=government,
            documents_agent=documents,
            evidence_service=evidence_service,
            nominatim=nominatim,
        )
