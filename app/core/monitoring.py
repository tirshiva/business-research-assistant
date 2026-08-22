"""Optional error monitoring. Secrets and request bodies are not attached."""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)


def init_error_monitoring(*, dsn: str, environment: str) -> None:
    """Initialize Sentry when ``SENTRY_DSN`` is set and the SDK is installed."""
    if not dsn.strip():
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning(
            "SENTRY_DSN is set but sentry-sdk is not installed; "
            "install the 'monitoring' extra to enable error monitoring"
        )
        return

    sentry_sdk.init(
        dsn=dsn.strip(),
        environment=environment,
        send_default_pii=False,
        integrations=[
            StarletteIntegration(failed_request_status_codes={*range(500, 600)}),
            FastApiIntegration(failed_request_status_codes={*range(500, 600)}),
        ],
    )
    logger.info("Error monitoring initialized environment=%s", environment)
