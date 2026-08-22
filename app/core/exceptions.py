"""Application-specific exceptions."""

from __future__ import annotations


class ExternalServiceError(Exception):
    """Base error for failures talking to external data providers."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status_code: int | None = None,
        details: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code
        self.details = details


class HttpRequestError(ExternalServiceError):
    """Raised when an upstream HTTP request fails with a non-success status."""


class ExternalTimeoutError(ExternalServiceError):
    """Raised when an upstream request exceeds the configured timeout."""


class RateLimitError(ExternalServiceError):
    """Raised when an upstream provider rate-limits the client."""


class MalformedResponseError(ExternalServiceError):
    """Raised when an upstream response cannot be parsed or validated."""


class DataUnavailableError(ExternalServiceError):
    """Raised when the provider has no usable data for the request."""


class InvestigationInputError(ValueError):
    """Raised when investigation graph input fails validation."""

    def __init__(self, message: str, *, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class LLMError(Exception):
    """Base error for LLM provider failures."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        details: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.details = details


class LLMConfigurationError(LLMError):
    """Raised when an LLM provider is missing required configuration."""


class LLMStructuredOutputError(LLMError):
    """Raised when structured LLM output cannot be validated."""


class PlannerError(Exception):
    """Raised when the research planner cannot produce a valid plan."""

    def __init__(
        self,
        message: str,
        *,
        details: str | None = None,
        attempts: int = 0,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.attempts = attempts
