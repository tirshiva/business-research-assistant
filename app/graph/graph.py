"""Investigation LangGraph definition."""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes.planner import create_planner_node
from app.graph.nodes.query_analyzer import query_analyzer
from app.graph.state import InvestigationState
from app.llm.base import LLMProvider


def build_investigation_graph(
    *,
    llm: LLMProvider | None = None,
) -> CompiledStateGraph:
    """Compile: START → query_analyzer → planner → END."""
    graph = StateGraph(InvestigationState)
    graph.add_node("query_analyzer", query_analyzer)
    graph.add_node("planner", create_planner_node(llm))
    graph.add_edge(START, "query_analyzer")
    graph.add_edge("query_analyzer", "planner")
    graph.add_edge("planner", END)
    return graph.compile()


@lru_cache
def get_investigation_graph() -> CompiledStateGraph:
    """Return a process-wide compiled investigation graph."""
    return build_investigation_graph()
