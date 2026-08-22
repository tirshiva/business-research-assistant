"""Task router node — select agents and prepare parallel research."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.graph.deps import ResearchOrchestrationDeps
from app.graph.progress import emit_progress
from app.graph.routing import select_executable_agents, select_unavailable_dimensions
from app.graph.state import InvestigationState

logger = get_logger(__name__)


def create_task_router_node(deps: ResearchOrchestrationDeps):
    """Build the task router that resolves coords and selects agents."""

    async def task_router(state: InvestigationState) -> dict[str, Any]:
        iteration = int(state.get("iteration") or 0) + 1
        investigation_id = state.get("investigation_id")

        if state.get("status") == "failed":
            logger.info(
                "Skipping task router because investigation failed (id=%s)",
                investigation_id,
            )
            return {"iteration": iteration, "routed_agents": []}

        research_plan = list(state.get("research_plan") or [])
        required_research = list(state.get("required_research") or [])
        if required_research:
            routed_agents = select_executable_agents(required_research)
        else:
            routed_agents = select_executable_agents(research_plan)
        unavailable = select_unavailable_dimensions(research_plan)

        agents_with_evidence = {
            item.get("agent")
            for item in (state.get("evidence") or [])
            if isinstance(item, dict) and item.get("agent")
        }
        routed_agents = [
            agent for agent in routed_agents if agent not in agents_with_evidence
        ]

        latitude = state.get("latitude")
        longitude = state.get("longitude")
        location = state.get("location")
        metadata = dict(state.get("metadata") or {})
        errors = list(state.get("validation_errors") or [])

        needs_coords = any(
            agent in {"weather", "competition", "geography"} for agent in routed_agents
        )
        if needs_coords and (latitude is None or longitude is None) and location:
            if deps.nominatim is None:
                for agent in list(routed_agents):
                    if agent in {"weather", "competition"}:
                        routed_agents.remove(agent)
                        if agent not in unavailable:
                            unavailable.append(agent)
                errors.append(
                    "Coordinates unavailable and nominatim was not configured"
                )
            else:
                try:
                    place = await deps.nominatim.geocode(location)
                    latitude = place.latitude
                    longitude = place.longitude
                    metadata["resolved_coordinates"] = {
                        "latitude": latitude,
                        "longitude": longitude,
                        "display_name": place.display_name,
                    }
                except ExternalServiceError as exc:
                    logger.warning(
                        "Geocoding failed id=%s error=%s",
                        investigation_id,
                        exc.message,
                    )
                    for agent in list(routed_agents):
                        if agent in {"weather", "competition"}:
                            routed_agents.remove(agent)
                            if agent not in unavailable:
                                unavailable.append(agent)
                    errors.append(f"geocoding_failed: {exc.message}")

        metadata["routed_agents"] = routed_agents
        metadata["unavailable_dimensions"] = unavailable

        logger.info(
            "Task router id=%s routed_agents=%s unavailable=%s",
            investigation_id,
            routed_agents,
            unavailable,
        )

        await emit_progress(
            deps,
            "mark_agents_running",
            investigation_id or "",
            routed_agents,
            unavailable,
        )

        return {
            "routed_agents": routed_agents,
            "unavailable_dimensions": unavailable,
            "latitude": latitude,
            "longitude": longitude,
            "validation_errors": errors,
            "status": "researching",
            "iteration": iteration,
            "metadata": metadata,
        }

    return task_router
