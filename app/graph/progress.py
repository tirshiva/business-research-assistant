"""Best-effort progress emission from graph nodes."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


async def emit_progress(deps: Any, method: str, *args: Any, **kwargs: Any) -> None:
    """Call a progress sink method; never fail the investigation graph."""
    sink = getattr(deps, "progress_sink", None)
    if sink is None:
        return
    fn = getattr(sink, method, None)
    if fn is None:
        return
    try:
        await fn(*args, **kwargs)
    except Exception:  # noqa: BLE001
        logger.exception("Investigation progress update failed method=%s", method)
