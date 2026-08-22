"""Helper to map exceptions into structured APIError models."""

from app.core.exceptions import ExternalServiceError
from app.models.errors import APIError


def api_error_from_exception(exc: ExternalServiceError) -> APIError:
    """Convert an application exception into a structured APIError."""
    return APIError(
        code=exc.__class__.__name__,
        message=exc.message,
        provider=exc.provider,
        status_code=exc.status_code,
        details=exc.details,
    )
