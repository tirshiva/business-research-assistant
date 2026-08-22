# Module 12 — Frontend and Production Deployment

A React investigation UI on top of the public FastAPI API, plus container
and CI packaging for production.

## Architecture

```text
React (static)
  → API Gateway / load balancer
    → FastAPI
      → LangGraph
        → AWS Bedrock (optional; local planner is the default)
      → PostgreSQL + pgvector
```

Use AWS only where it is clearly useful:

| Need | Service |
|---|---|
| HTTPS + routing | Application Load Balancer / API Gateway |
| API compute | ECS/Fargate (container already provided) |
| Database | RDS PostgreSQL with pgvector, or self-managed Postgres |
| LLM | Bedrock when `LLM_PROVIDER=bedrock` |
| Object storage | S3 for future document uploads (not required for the sample corpus) |
| Frontend CDN | S3 + CloudFront, or nginx in the same cluster |
| Logs / errors | CloudWatch + optional Sentry (`SENTRY_DSN`) |

Secrets stay in a secrets manager or environment variables. They are never
returned by the API. Production disables `/docs`, `/redoc`, and `/openapi.json`.
LangGraph state, system prompts, API keys, and database credentials are not
exposed to the browser.

## Frontend

`web/` is a Vite + React app:

- Investigation form: business type, location, target customer, budget, question
- Progress: lifecycle stage, running/completed/failed agents, evidence count,
  research iteration
- Results: opportunity score, dimensions, recommendation, confidence,
  opportunities, risks, unknowns
- Evidence explorer: claim → evidence → source → timestamp

Local UI:

```bash
cd web
npm install
npm run dev
```

The Vite dev server proxies `/investigations` and `/health` to
`http://127.0.0.1:8000`. Run the API separately (`uv run uvicorn app.main:app`).

Docker Compose serves the UI at http://localhost:8080 (nginx reverse-proxies
the API).

## Health

- `GET /health` — liveness
- `GET /ready` — database readiness

## Configuration

| Variable | Purpose |
|---|---|
| `CORS_ORIGINS` | Comma-separated browser origins |
| `SENTRY_DSN` | Optional Sentry DSN (`uv sync --extra monitoring`) |
| `APP_ENV=production` | Hides OpenAPI docs |
| `VITE_API_BASE_URL` | Empty = same origin (nginx); set only for a split API host |

## CI/CD

`.github/workflows/ci.yml` runs Ruff + pytest, builds the React app, and on
push builds the API and web images.
