"""Mapping from planner research tasks to executable agents."""

from __future__ import annotations

# Tasks the system can currently execute via dedicated agents.
EXECUTABLE_AGENT_TASKS: frozenset[str] = frozenset(
    {
        "weather",
        "geography",
        "competition",
        "government_data",
        "documents",
    }
)

# Planner may request these, but no specialized agent exists yet.
UNSUPPORTED_RESEARCH_TASKS: frozenset[str] = frozenset(
    {
        "demographics",
        "infrastructure",
    }
)


def select_executable_agents(research_plan: list[str]) -> list[str]:
    """Return ordered unique agent names implied by the research plan."""
    selected: list[str] = []
    for task in research_plan:
        name = task.strip().lower()
        if name in EXECUTABLE_AGENT_TASKS and name not in selected:
            selected.append(name)
    return selected


def select_unavailable_dimensions(research_plan: list[str]) -> list[str]:
    """Return planned tasks that cannot be executed by current agents."""
    unavailable: list[str] = []
    for task in research_plan:
        name = task.strip().lower()
        if (
            name in UNSUPPORTED_RESEARCH_TASKS
            and name not in unavailable
            or (
                name
                and name not in EXECUTABLE_AGENT_TASKS
                and name not in UNSUPPORTED_RESEARCH_TASKS
                and name not in unavailable
            )
        ):
            unavailable.append(name)
    return unavailable
