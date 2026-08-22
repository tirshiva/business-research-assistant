"""Investigation LangGraph definition with multi-agent orchestration."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from app.graph.deps import ResearchOrchestrationDeps
from app.graph.nodes.evidence_collection import create_evidence_collection_node
from app.graph.nodes.planner import create_planner_node
from app.graph.nodes.query_analyzer import query_analyzer
from app.graph.nodes.research_agent import create_research_agent_node
from app.graph.nodes.task_router import create_task_router_node
from app.graph.state import InvestigationState
from app.llm.base import LLMProvider


def build_investigation_graph(
    *,
    llm: LLMProvider | None = None,
    deps: ResearchOrchestrationDeps | None = None,
) -> CompiledStateGraph:
    """Compile the multi-agent investigation graph.

    Flow::

        START → query_analyzer → planner → task_router
              → parallel research_agent (Send fan-out)
              → evidence_collection → END
    """
    orchestration = deps or ResearchOrchestrationDeps.mock()

    graph = StateGraph(InvestigationState)
    graph.add_node("query_analyzer", query_analyzer)
    graph.add_node("planner", create_planner_node(llm))
    graph.add_node("task_router", create_task_router_node(orchestration))
    graph.add_node("research_agent", create_research_agent_node(orchestration))
    graph.add_node(
        "evidence_collection",
        create_evidence_collection_node(orchestration),
    )

    graph.add_edge(START, "query_analyzer")
    graph.add_edge("query_analyzer", "planner")
    graph.add_edge("planner", "task_router")
    graph.add_conditional_edges("task_router", _fan_out_research)
    graph.add_edge("research_agent", "evidence_collection")
    graph.add_edge("evidence_collection", END)
    return graph.compile()


def _fan_out_research(state: InvestigationState) -> list[Send]:
    """Dynamically fan out to selected agents, or skip to evidence collection."""
    agents = list(state.get("routed_agents") or [])
    if not agents:
        return [Send("evidence_collection", _snapshot_state(state))]

    work_items = [
        Send(
            "research_agent",
            {
                "investigation_id": state["investigation_id"],
                "user_query": state["user_query"],
                "business_type": state.get("business_type"),
                "location": state.get("location"),
                "target_customer": state.get("target_customer"),
                "latitude": state.get("latitude"),
                "longitude": state.get("longitude"),
                "agent_name": agent_name,
            },
        )
        for agent_name in agents
    ]
    return work_items


def _snapshot_state(state: InvestigationState) -> dict[str, Any]:
    """Copy state for a passthrough Send when no agents are routed."""
    return {
        "investigation_id": state["investigation_id"],
        "user_query": state["user_query"],
        "business_type": state.get("business_type"),
        "location": state.get("location"),
        "objective": state.get("objective"),
        "target_customer": state.get("target_customer"),
        "research_plan": list(state.get("research_plan") or []),
        "latitude": state.get("latitude"),
        "longitude": state.get("longitude"),
        "routed_agents": list(state.get("routed_agents") or []),
        "agent_results": list(state.get("agent_results") or []),
        "agent_runs": list(state.get("agent_runs") or []),
        "unavailable_dimensions": list(state.get("unavailable_dimensions") or []),
        "evidence": list(state.get("evidence") or []),
        "contradictions": list(state.get("contradictions") or []),
        "analysis": state.get("analysis"),
        "opportunity_score": state.get("opportunity_score"),
        "recommendation": state.get("recommendation"),
        "confidence": state.get("confidence"),
        "validation_errors": list(state.get("validation_errors") or []),
        "iteration": state.get("iteration") or 0,
        "status": state.get("status") or "researching",
        "metadata": dict(state.get("metadata") or {}),
    }


def get_investigation_graph() -> CompiledStateGraph:
    """Return a graph with mock research deps (tests / fallback).

    Production should call :func:`build_investigation_graph` with real deps.
    """
    return build_investigation_graph(deps=ResearchOrchestrationDeps.mock())
