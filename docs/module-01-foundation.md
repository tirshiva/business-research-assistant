# Documentation

Additional project documentation lives in this directory.

## Module 01 — Project Foundation

This module establishes the production-oriented Python backend foundation:

- FastAPI application bootstrap (`app/main.py`)
- Configuration via Pydantic Settings (`app/config/`)
- Centralized logging (`app/core/logging.py`)
- Health endpoint (`GET /health`)
- Test suite, Docker packaging, and Ruff quality gates

See the root [README.md](../README.md) for setup and run instructions.

## Logging usage in future modules

```python
from app.core.logging import get_logger

logger = get_logger(__name__)
logger.info("Starting research workflow")
```

Log records include timestamp, level, module name, and message.
