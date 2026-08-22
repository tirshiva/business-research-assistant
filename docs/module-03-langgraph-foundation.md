# Module 03 — LangGraph Foundation

Minimal executable LangGraph with a typed investigation state.

## Graph

```text
START → query_analyzer → END
```

No planner, agents, RAG, external API calls, or scoring in this module.

## State

`app/graph/state.py` defines `InvestigationState` (TypedDict) with:

- identity / input: `investigation_id`, `user_query`
- structured ask: `business_type`, `location`, `objective`
- research slots: `research_plan`, `evidence`, `contradictions`, `analysis`
- decision slots: `opportunity_score`, `recommendation`, `confidence`
- control: `validation_errors`, `iteration`, `status`

Use `create_initial_state(user_query)` to build a valid starting state.

## Query analyzer

`app/graph/nodes/query_analyzer.py` uses deterministic heuristics (no LLM) to
populate `business_type`, `location`, `objective`, and set
`status="query_analyzed"`.

## Execution service

```python
from app.services.investigation import InvestigationService

service = InvestigationService()
result = await service.run(
    {"user_query": "Is Sector 62 Noida a good location for a cloud kitchen?"}
)
```

Returns a validated `InvestigationResult` mirroring `InvestigationState`.

## Tests

```bash
uv run pytest tests/test_investigation_graph.py -v
```
