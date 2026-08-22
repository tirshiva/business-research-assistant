# Module 02 — External Data Layer

Reusable async clients for public data sources. No LangGraph, LLMs, or business
scoring in this module.

## Clients

### Open-Meteo (`app/services/external/open_meteo.py`)

- `get_current_weather(latitude, longitude)`
- `get_hourly_forecast(latitude, longitude)`
- `get_daily_forecast(latitude, longitude)`
- `get_forecast(latitude, longitude)` — current + hourly + daily
- `get_historical_weather(latitude, longitude, start_date, end_date)`

Returns `WeatherData` (application model), never raw provider payloads.

### Nominatim (`app/services/external/nominatim.py`)

- `geocode(address)` — address → coordinates (`LocationData`)
- `reverse_geocode(latitude, longitude)` — coordinates → address

Uses a descriptive `User-Agent` and paces requests (~1 req/s) to respect
Nominatim usage policy. If Nominatim returns 403/5xx (common on the public
instance), `FallbackGeocoder` retries via Open-Meteo geocoding.

## Shared infrastructure

| Component | Location |
|---|---|
| Async HTTP client | `app/core/http.py` |
| Cache protocol + in-memory backend | `app/core/cache/` |
| Exceptions | `app/core/exceptions.py` |
| Models | `app/models/weather.py`, `location.py`, `errors.py` |

## Example

```python
location = await nominatim.geocode("Sector 62, Noida")
weather = await open_meteo.get_forecast(
    latitude=location.latitude,
    longitude=location.longitude,
)
```

Clients are also attached to the FastAPI app at startup:

- `app.state.open_meteo`
- `app.state.nominatim`
- `app.state.http_client`
- `app.state.cache`

## Tests

```bash
# Unit tests (mocked HTTP — default)
uv run pytest

# Optional live API integration test
RUN_INTEGRATION_TESTS=true uv run pytest -m integration
```
