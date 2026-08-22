# Module 08 — Business Analysis and Opportunity Scoring

Transform validated evidence into structured insights and a deterministic
opportunity score.

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
      └─ FAIL → planner
```

The analysis node receives **only validated evidence** already stored on
investigation state. Research agents still do not score or recommend.

## Analysis Agent

`AnalysisAgent` produces qualitative:

- observations
- opportunities
- risks
- unknowns
- inferred insights

Every **inferred** insight must cite supporting `evidence_id` values. Unknown
evidence IDs returned by an LLM are stripped; inferred items with no remaining
citations are dropped.

The LLM (local or Bedrock) must **not** invent the numerical score. Insights
use `AnalysisInsights`; scores are computed in Python.

## Scoring

Configurable dimensions (`ScoringConfig` / settings weights):

| Dimension | Default weight |
|---|---|
| demand | 0.25 |
| competition | 0.20 |
| accessibility | 0.15 |
| infrastructure | 0.15 |
| market_indicators | 0.15 |
| risk | 0.10 |

Each dimension records:

- `score` (0–10)
- `weight` (normalized)
- `supporting_evidence` (evidence IDs)
- `confidence` (0–1)
- `missing` when no validated evidence applies

`risk` is scored as **favorability** (10 = lower risk).

Overall score is a weighted average of **non-missing** dimensions:

```text
overall = sum(score_i * weight_i) / sum(weight_i)
```

Same evidence + config always yields the same number.

## Recommendation

| Score | Label |
|---|---|
| 8.5–10 | STRONG OPPORTUNITY |
| 7–8.49 | PROMISING |
| 5–6.99 | PROCEED WITH CAUTION |
| 3–4.99 | WEAK OPPORTUNITY |
| 0–2.99 | LOW OPPORTUNITY |

If any **critical** dimension lacks evidence (default: demand, competition,
accessibility), the recommendation is `INSUFFICIENT DATA`. The numeric score
is still computed from available dimensions for traceability.

## Example

```python
from app.agents.analysis import AnalysisAgent
from app.evidence import EvidenceService
from app.scoring import score_opportunity

evidence = await evidence_service.list_investigation_evidence(investigation_id)
result = await AnalysisAgent().run(evidence)
# result.overall_score, result.recommendation, result.insights
# result.scorecard["dimensions"] traces weights, scores, and evidence IDs
```

On investigation results:

- `opportunity_score` — deterministic 0–10
- `recommendation` — band or `INSUFFICIENT DATA`
- `analysis` — cited qualitative summary
- `metadata["opportunity_scorecard"]` — full trace
