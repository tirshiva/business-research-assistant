"""Parallel research worker node executed via LangGraph Send."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.agents.competition import CompetitionAgentInput
from app.agents.documents import DocumentsAgentInput
from app.agents.geography import GeographyAgentInput
from app.agents.government import GovernmentDataAgentInput
from app.agents.schemas import AgentResult
from app.agents.weather import WeatherAgentInput
from app.core.logging import get_logger
from app.graph.deps import ResearchOrchestrationDeps
from app.graph.state import AgentWorkItem

logger = get_logger(__name__)


def create_research_agent_node(deps: ResearchOrchestrationDeps):
    """Build an isolated research worker that runs a single selected agent."""

    async def research_agent(state: AgentWorkItem) -> dict[str, Any]:
        agent_name = state["agent_name"]
        investigation_id = state["investigation_id"]
        started_at = datetime.now(UTC)
        findings_count = 0
        status = "failed"
        error: str | None = None
        unavailable: list[str] = []

        logger.info(
            "Agent start investigation_id=%s agent=%s start_time=%s",
            investigation_id,
            agent_name,
            started_at.isoformat(),
        )

        try:
            agent = deps.get_agent(agent_name)
            # Isolation: worker only invokes the selected agent object, which
            # itself only exposes its declared allowed_tools.
            payload = _build_agent_input(agent_name, state)
            result: AgentResult = await agent.run(payload)
            findings_count = len(result.findings)
            status = result.status
            if result.errors:
                error = "; ".join(result.errors)
            if result.status in {"failed", "data_unavailable"}:
                unavailable = [agent_name]
            agent_result_payload = result.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - isolate agent failures
            status = "failed"
            error = str(exc)
            unavailable = [agent_name]
            agent_result_payload = {
                "agent": agent_name,
                "findings": [],
                "sources": [],
                "confidence": 0.0,
                "status": "failed",
                "errors": [error],
                "allowed_tools": [],
            }
            logger.exception(
                "Agent crashed investigation_id=%s agent=%s",
                investigation_id,
                agent_name,
            )

        completed_at = datetime.now(UTC)
        allowed_tools: list[str] = []
        try:
            allowed_tools = list(deps.get_agent(agent_name).allowed_tools)
        except Exception:  # noqa: BLE001
            allowed_tools = []

        run_record = {
            "investigation_id": investigation_id,
            "agent": agent_name,
            "start_time": started_at.isoformat(),
            "completion_time": completed_at.isoformat(),
            "status": status,
            "error": error,
            "findings_count": findings_count,
            "allowed_tools": allowed_tools,
        }

        logger.info(
            "Agent complete investigation_id=%s agent=%s completion_time=%s "
            "status=%s error=%s findings_count=%s",
            investigation_id,
            agent_name,
            completed_at.isoformat(),
            status,
            error,
            findings_count,
        )

        return {
            "agent_results": [agent_result_payload],
            "agent_runs": [run_record],
            "unavailable_dimensions": unavailable,
        }

    return research_agent


def _build_agent_input(agent_name: str, state: AgentWorkItem) -> Any:
    location = state.get("location") or "unknown location"
    business_type = state.get("business_type") or "business"
    latitude = state.get("latitude")
    longitude = state.get("longitude")

    if agent_name == "weather":
        if latitude is None or longitude is None:
            raise ValueError("weather agent requires latitude/longitude")
        return WeatherAgentInput(
            location=location,
            latitude=latitude,
            longitude=longitude,
        )
    if agent_name == "geography":
        return GeographyAgentInput(
            location=location,
            latitude=latitude,
            longitude=longitude,
        )
    if agent_name == "competition":
        if latitude is None or longitude is None:
            raise ValueError("competition agent requires latitude/longitude")
        return CompetitionAgentInput(
            business_type=business_type,
            location=location,
            latitude=latitude,
            longitude=longitude,
        )
    if agent_name == "government_data":
        return GovernmentDataAgentInput(
            query=state.get("user_query") or location,
            location=state.get("location"),
            business_type=state.get("business_type"),
        )
    if agent_name == "documents":
        return DocumentsAgentInput(
            query=state.get("user_query") or location,
            location=state.get("location"),
            business_type=state.get("business_type"),
        )
    raise ValueError(f"Unsupported agent '{agent_name}'")
