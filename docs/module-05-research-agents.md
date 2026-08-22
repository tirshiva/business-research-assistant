# Module 05 — Real-World Research Agents

Independent research agents that call public tools and return validated
`AgentResult` envelopes. Agents do **not** score opportunities or make
business recommendations.

## Agents

| Agent | Tools | Notes |
|---|---|---|
| Weather | Open-Meteo | Forecast / historical weather |
| Geography | Nominatim | Geocode, reverse geocode, surrounding context |
| Competition | Pluggable business search (Overpass/OSM default) | Public POIs only — no scraping |
| Government Data | data.gov.in CKAN catalog | Metadata search; structured unavailable if API fails |

## Common output

```json
{
  "agent": "weather",
  "findings": [],
  "sources": [],
  "confidence": 0.0,
  "status": "completed"
}
```

Statuses: `completed`, `partial`, `failed`, `data_unavailable`.

## Example

```python
from app.agents import WeatherAgent, WeatherAgentInput

result = await weather_agent.run(
    WeatherAgentInput(
        location="Sector 62, Noida",
        latitude=28.62,
        longitude=77.36,
        forecast_days=7,
    )
)
```

On the running FastAPI app:

- `app.state.weather_agent`
- `app.state.geography_agent`
- `app.state.competition_agent`
- `app.state.government_data_agent`
