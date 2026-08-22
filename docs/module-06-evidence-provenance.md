# Module 06 — Evidence and Provenance System

Standardized evidence representation for all research agents.

## Models

### Evidence

- `evidence_id`
- `investigation_id`
- `agent`
- `claim`
- `value`
- `claim_kind` — `FACT` | `INFERENCE` | `RECOMMENDATION`
- `source` — `SourceRecord`
- `source_url`
- `retrieved_at`
- `confidence`
- `metadata`

### SourceRecord

- `name`
- `source_type` — api / dataset / document / map / catalog / other
- `url`
- `retrieved_at`
- `reliability` — high / medium / low / unknown

### Contradiction

Explicit conflict object when FACT claims disagree (never silently resolved).

## Repository

`EvidenceRepository` protocol + `InMemoryEvidenceRepository` (PostgreSQL-ready).

## Validation

`EvidenceValidator` checks:

- missing source
- missing timestamp
- low confidence
- duplicate evidence
- contradictory evidence
- stale data

## Usage

```python
from app.evidence import EvidenceService, build_evidence

stored, validation = await evidence_service.submit(
    build_evidence(
        investigation_id=investigation_id,
        agent="competition",
        claim="competition.level",
        value="LOW",
        source_name="OpenStreetMap",
        source_url="https://www.openstreetmap.org/",
        confidence=0.8,
        claim_kind="FACT",
    )
)

provenance = await evidence_service.get_claim_provenance(
    investigation_id,
    "competition.level",
)
```

Convert agent output:

```python
await evidence_service.submit_agent_result(
    investigation_id=investigation_id,
    result=agent_result,
    claim_kind="FACT",
)
```

On the FastAPI app: `app.state.evidence_service`, `app.state.evidence_repository`.
