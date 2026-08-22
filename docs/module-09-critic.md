# Module 09 — Critic and Self-Correction Workflow

Quality-control loop that runs after analysis and before the investigation
finishes.

## Graph

```text
START
  → query_analyzer
  → planner
  → task_router
  → parallel research_agent
  → evidence_collection
  → analysis
  → critic
      ├─ PASS → END
      └─ FAIL → planner   (explicit cyclic edge)
```

The graph supports **Research → Critic → Research** via `route_after_critic`.

## Critic checks

Deterministic Python evaluation of:

1. Evidence coverage
2. Source quality
3. Data freshness
4. Contradictions
5. Unsupported claims
6. Logical consistency (recommendation vs numeric score)
7. Missing critical information

## Output

```json
{
  "status": "PASS",
  "confidence": 0.0,
  "issues": [],
  "required_research": []
}
```

Stored on investigation results as `critic_status`, `critic_confidence`,
`critic_issues`, `required_research`, and `metadata["critic"]`.

Example issue: `"Competition data is insufficient."` → `required_research`
includes `competition`. The planner merges that task, the router runs the
competition agent (skipping agents that already have evidence), evidence is
validated/merged, and the critic runs again.

## Maximum iterations

`MAX_RESEARCH_ITERATIONS` (default **3**) counts research cycles
(evidence-collection passes).

If the critic still FAILs at the cap:

- recommendation becomes `INSUFFICIENT DATA`
- the graph **ends** (no further planner loops)

## Example

```python
from app.graph import build_investigation_graph, ResearchOrchestrationDeps
from app.services.investigation import InvestigationService

result = await InvestigationService(
    graph=build_investigation_graph(deps=ResearchOrchestrationDeps.mock())
).run({"user_query": "Is Sector 62, Noida a good location for a cloud kitchen?"})

# result.critic_status in {"PASS", "FAIL"}
# result.metadata["critic"]["required_research"]
```
