# India Business Research & Decision Agent

AI-powered backend that researches real-world Indian business questions using
public APIs, government datasets, maps, documents, and other publicly available
sources. Future modules will orchestrate specialized research agents with
LangGraph.

Current modules:

- **Module 01** — Project foundation (FastAPI, settings, logging, Docker)
- **Module 02** — External data layer (Open-Meteo + Nominatim clients)
- **Module 03** — LangGraph foundation (typed state + query analyzer)
- **Module 04** — Research planner (structured ResearchPlan via LLM abstraction)
- **Module 05** — Real-world research agents (weather, geography, competition, government data)
- **Module 06** — Evidence and provenance system
- **Module 07** — Multi-agent LangGraph orchestration
- **Module 08** — Business analysis and opportunity scoring
- **Module 09** — Critic and self-correction workflow
- **Module 10** — Persistence and FastAPI investigation API
- **Module 11** — Government document RAG (pgvector + documents agent)

## Features

- FastAPI application with `GET /health`
- Pydantic Settings-based configuration (no hardcoded secrets)
- Centralized structured logging
- Reusable async HTTP client with shared connection pool
- In-memory cache abstraction (Redis-ready interface)
- Open-Meteo weather client (`WeatherData` models)
- Nominatim geocoding client (`LocationData` models)
- LangGraph investigation graph (`START → query_analyzer → planner → END`)
- Typed `InvestigationState` with deterministic query analysis
- Research planner producing validated `ResearchPlan` (local or Bedrock LLM)
- Specialized research agents with typed I/O, tools, confidence, and sources
- Evidence repository with validation, contradictions, and claim provenance
- Multi-agent LangGraph orchestration with dynamic routing and parallel research
- Analysis agent with cited insights and deterministic weighted opportunity scoring
- FastAPI investigation API (`POST/GET /investigations`) with PostgreSQL persistence
- Critic quality-control loop with cyclic re-research and a max-iteration halt
- Document RAG (parse → chunk → embed → pgvector / SQLite cosine) with cited passages
- pytest coverage with mocked HTTP/LLM; optional live integration tests
- Docker + docker-compose for local development
- Ruff for linting and formatting
- `uv` for dependency management

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker (optional, for containerized runs)

## Local setup

```bash
# Clone / enter the project directory
cd "India Business Research & Decision Agent"

# Create a virtual environment and install dependencies (including dev tools)
uv sync

# Copy example environment variables and adjust as needed
cp .env.example .env
```

Update `NOMINATIM_USER_AGENT` in `.env` with a real contact address before
calling the public Nominatim service.

## Environment variables

| Variable | Description | Example |
|---|---|---|
| `APP_NAME` | Application display name | `India Business Research & Decision Agent` |
| `APP_ENV` | Runtime environment | `development` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `DATABASE_URL` | PostgreSQL URL (`postgresql+asyncpg://...`) | `postgresql+asyncpg://user:password@localhost:5432/ibrda` |
| `OPEN_METEO_BASE_URL` | Open-Meteo forecast API base URL | `https://api.open-meteo.com/v1` |
| `OPEN_METEO_ARCHIVE_BASE_URL` | Open-Meteo historical API base URL | `https://archive-api.open-meteo.com/v1` |
| `NOMINATIM_BASE_URL` | Nominatim API base URL | `https://nominatim.openstreetmap.org` |
| `NOMINATIM_USER_AGENT` | Required descriptive User-Agent | `IndiaBusinessResearchDecisionAgent/0.1 (you@example.com)` |
| `HTTP_TIMEOUT_SECONDS` | Upstream HTTP timeout | `30` |
| `CACHE_TTL_SECONDS` | Default in-memory cache TTL | `600` |
| `EVIDENCE_LOW_CONFIDENCE_AS_ERROR` | Treat low confidence as a hard error | `false` |
| `SCORE_WEIGHT_DEMAND` | Opportunity score weight: demand | `0.25` |
| `SCORE_WEIGHT_COMPETITION` | Opportunity score weight: competition | `0.20` |
| `SCORE_WEIGHT_ACCESSIBILITY` | Opportunity score weight: accessibility | `0.15` |
| `SCORE_WEIGHT_INFRASTRUCTURE` | Opportunity score weight: infrastructure | `0.15` |
| `SCORE_WEIGHT_MARKET_INDICATORS` | Opportunity score weight: market indicators | `0.15` |
| `SCORE_WEIGHT_RISK` | Opportunity score weight: risk favorability | `0.10` |
| `SCORE_CRITICAL_DIMENSIONS` | Dimensions required to avoid `INSUFFICIENT DATA` | `demand,competition,accessibility` |
| `MAX_RESEARCH_ITERATIONS` | Critic self-correction cap before halt | `3` |
| `RAG_EMBEDDING_DIM` | Hashing embedding size (must match pgvector column) | `64` |
| `RAG_CHUNK_SIZE` | Character chunk size | `420` |
| `RAG_CHUNK_OVERLAP` | Overlap between chunks | `80` |
| `RAG_TOP_K` | Retriever hit count | `5` |
| `RAG_SEED_ON_STARTUP` | Ingest sample public corpus if empty | `true` |
| `RUN_INTEGRATION_TESTS` | Enable live API tests when `true` | `false` |

See `.env.example` for a complete template. Never commit real secrets.

## Run the API

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open:

- Health: http://localhost:8000/health
- Interactive docs: http://localhost:8000/docs

Create an investigation:

```bash
curl -X POST http://localhost:8000/investigations \
  -H 'Content-Type: application/json' \
  -d '{"query":"Is Sector 62, Noida a good location for a cloud kitchen?"}'
```

### Run with Docker Compose

```bash
docker compose up --build
```

The Compose `db` service uses `pgvector/pgvector:pg16` so `CREATE EXTENSION vector` succeeds.

## Using the investigation graph

```python
from app.services.investigation import InvestigationService
from app.graph.graph import build_investigation_graph
from app.graph.deps import ResearchOrchestrationDeps
from app.llm.local import LocalLLMProvider

service = InvestigationService(
    graph=build_investigation_graph(
        llm=LocalLLMProvider(),
        deps=ResearchOrchestrationDeps.mock(),
    )
)
result = await service.run(
    {
        "user_query": (
            "Is Sector 62, Noida a good location for a cloud kitchen "
            "targeting office workers?"
        )
    }
)
# result.status in {"completed", "partial"}
# result.routed_agents / result.agent_results / result.evidence
# result.opportunity_score, result.recommendation, result.analysis
```

## Using the external clients

```python
from app.core.http import AsyncHttpClient
from app.services.external import NominatimClient, OpenMeteoClient

async with AsyncHttpClient() as http:
    nominatim = NominatimClient(http, user_agent="YourApp/0.1 (you@example.com)")
    open_meteo = OpenMeteoClient(http)

    location = await nominatim.geocode("Sector 62, Noida")
    weather = await open_meteo.get_forecast(
        latitude=location.latitude,
        longitude=location.longitude,
    )
```

Inside a running FastAPI app, the same clients are available on:

- `request.app.state.nominatim`
- `request.app.state.open_meteo`

## Run tests

```bash
# Unit tests (mocked HTTP — no live network calls)
uv run pytest

# Optional live integration tests
RUN_INTEGRATION_TESTS=true uv run pytest -m integration
```

## Code quality

```bash
uv run ruff check .
uv run ruff format --check .
```

Auto-fix formatting:

```bash
uv run ruff format .
uv run ruff check --fix .
```

## Project structure

```text
app/
  api/routes/              # health + investigations
  config/                  # Pydantic Settings
  core/
    cache/                 # CacheBackend + InMemoryCache
    exceptions.py          # Application exceptions
    http.py                # Shared async HTTP client
    logging.py             # Centralized logging
  graph/
    state.py               # InvestigationState TypedDict
    nodes/                 # analyzer, planner, router, research, evidence, analysis, critic
    graph.py               # Multi-agent orchestration graph
    routing.py             # Plan task → agent mapping
    deps.py                # Injected agent/evidence dependencies
  db/                      # SQLAlchemy models, sessions, investigation store
  critic/                  # Quality-control checks and PASS/FAIL verdict
  agents/                  # weather, geography, competition, government, documents, analysis
  rag/                     # Document parse/chunk/embed/pgvector retrieve
  scoring/                 # Deterministic dimension weights and overall score
  evidence/                # Evidence models, repository, validator, service
  llm/                     # LLMProvider abstraction (local, bedrock)
  models/                  # WeatherData, LocationData, ResearchPlan, AgentResult
  services/
    external/              # Open-Meteo, Nominatim, Overpass, data.gov.in
    investigation.py       # Graph execution service
    investigation_app.py   # Persist + public API orchestration
    planner.py             # ResearchPlanner
  main.py                  # FastAPI entrypoint
tests/                     # Unit + optional integration tests
docs/                      # Module documentation
```

## Out of scope (later modules)

- Frontend

## License

Proprietary — all rights reserved unless otherwise stated.
