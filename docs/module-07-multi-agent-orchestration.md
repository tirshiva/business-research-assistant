# Module 07 — Multi-Agent LangGraph Orchestration

Integrate research agents into a dynamic, partially parallel LangGraph workflow.

## Graph

```text
START
  → query_analyzer
  → planner
  → task_router
  → parallel research_agent (LangGraph Send fan-out)
  → evidence_collection
  → END
```

## Dynamic routing

`task_router` reads `research_plan` and selects only executable agents:

- weather
- geography
- competition
- government_data

Unsupported planned tasks (`demographics`, `infrastructure`, `documents`) are recorded in `unavailable_dimensions`.

## Parallel execution

Selected agents are dispatched concurrently via `langgraph.types.Send` to the shared `research_agent` worker node. Results merge through state reducers (`agent_results`, `agent_runs`).

## Partial failure

If one agent fails:

- failure is logged and stored in `agent_runs`
- other agents continue
- the dimension is added to `unavailable_dimensions`
- final status becomes `partial` when some agents succeed

## Observability

Each agent run records:

- investigation_id
- agent
- start_time
- completion_time
- status
- error
- findings_count
- allowed_tools

## Example

```python
from app.graph import build_investigation_graph, ResearchOrchestrationDeps
from app.services.investigation import InvestigationService

service = InvestigationService(
    graph=build_investigation_graph(deps=ResearchOrchestrationDeps.mock())
)
result = await service.run(
    {
        "user_query": (
            "Is Sector 62, Noida a good location for a cloud kitchen "
            "targeting office workers?"
        )
    }
)
# result.routed_agents, result.agent_results, result.evidence
```
