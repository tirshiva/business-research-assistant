"""Application services package."""

from app.services.external import NominatimClient, OpenMeteoClient
from app.services.planner import ResearchPlanner

__all__ = [
    "InvestigationService",
    "NominatimClient",
    "OpenMeteoClient",
    "ResearchPlanner",
]


def __getattr__(name: str):
    """Lazy export to avoid circular imports with the graph package."""
    if name == "InvestigationService":
        from app.services.investigation import InvestigationService

        return InvestigationService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
