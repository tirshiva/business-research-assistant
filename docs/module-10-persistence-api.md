# Module 10 — Persistence and FastAPI API

Expose investigations through FastAPI and persist results in PostgreSQL
(SQLite is used automatically in unit tests).

## Lifecycle

`CREATED` → `PLANNING` → `RESEARCHING` → `VALIDATING` → `ANALYZING` →
`REVIEWING` → `COMPLETED` | `FAILED`

These statuses are stored on the investigation record. LangGraph internal
state is never returned by the API.

## Tables

- `investigations` — query, lifecycle, scores, critic result, report
- `research_tasks` — planned/executed task status
- `evidence` — validated evidence items
- `contradictions` — recorded FACT conflicts
- `recommendations` — recommendation snapshots

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/investigations` | Create + start research (`202`) |
| GET | `/investigations/{id}` | Public snapshot |
| GET | `/investigations/{id}/status` | Lifecycle status |
| GET | `/investigations/{id}/evidence` | Evidence list |
| GET | `/investigations/{id}/report` | Final report |
| POST | `/investigations/{id}/research` | Additional research pass |

Request body for create:

```json
{ "query": "Is Sector 62, Noida a good location for a cloud kitchen?" }
```

Errors use `{ "code", "message", "details?" }`:

- `400` invalid request
- `404` investigation not found
- `409` investigation already running
- `500` unexpected application error

## Example

```bash
curl -X POST http://localhost:8000/investigations \
  -H 'Content-Type: application/json' \
  -d '{"query":"Is Sector 62, Noida a good location for a cloud kitchen?"}'

curl http://localhost:8000/investigations/{id}/status
curl http://localhost:8000/investigations/{id}/evidence
curl http://localhost:8000/investigations/{id}/report
```
