# Module 04 — Research Planner

Convert a natural-language business question into a validated `ResearchPlan`.

## Graph

```text
START → query_analyzer → planner → END
```

## Output model

`ResearchPlan` (`app/models/research_plan.py`):

- `business_type`
- `location`
- `objective`
- `target_customer`
- `research_tasks` — subset of:
  - demographics
  - competition
  - geography
  - infrastructure
  - weather
  - government_data
  - documents

## LLM abstraction

Providers implement `app.llm.base.LLMProvider.generate_structured(...)`.

| Provider | Config value | Notes |
|---|---|---|
| Local (default) | `LLM_PROVIDER=local` | Deterministic structured planner for MVP |
| AWS Bedrock | `LLM_PROVIDER=bedrock` | Requires `boto3`, credentials, `BEDROCK_MODEL_ID` |

The planner never depends on a concrete vendor SDK.

## Retries

On structured-output / validation failure the planner retries according to:

- `PLANNER_MAX_RETRIES`
- `PLANNER_RETRY_BACKOFF_SECONDS`

Failures are recorded on investigation state (`validation_errors`, `metadata.planner_error`).
Invalid plans are never returned silently.

## Example

```python
from app.services.investigation import InvestigationService
from app.llm.local import LocalLLMProvider
from app.graph.graph import build_investigation_graph

service = InvestigationService(graph=build_investigation_graph(llm=LocalLLMProvider()))
result = await service.run(
    {
        "user_query": (
            "Is Sector 62, Noida a good location for a cloud kitchen "
            "targeting office workers?"
        )
    }
)
# result.status == "planned"
# result.research_plan includes demographics, competition, geography, ...
```
