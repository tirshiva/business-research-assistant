"""Public investigation progress updates (no LangGraph state)."""

from __future__ import annotations

from app.core.logging import get_logger
from app.db.store import InvestigationStore

logger = get_logger(__name__)


class InvestigationProgressSink:
    """Persist lifecycle and agent progress for the web UI."""

    def __init__(self, store: InvestigationStore) -> None:
        self._store = store

    async def mark_stage(self, investigation_id: str, status: str) -> None:
        await self._store.set_status(investigation_id, status)

    async def record_plan(
        self,
        investigation_id: str,
        *,
        plan: list[str],
        business_type: str | None,
        location: str | None,
        target_customer: str | None,
    ) -> None:
        await self._store.update_public_fields(
            investigation_id,
            status="PLANNING",
            plan=plan,
            business_type=business_type,
            location=location,
            target_customer=target_customer,
        )
        await self._store.replace_tasks(
            investigation_id,
            [(name, "pending") for name in plan],
        )

    async def mark_agents_running(
        self,
        investigation_id: str,
        agents: list[str],
        unavailable: list[str] | None = None,
    ) -> None:
        await self._store.set_status(investigation_id, "RESEARCHING")
        for name in agents:
            await self._store.upsert_task(investigation_id, name, "running")
        for name in unavailable or []:
            await self._store.upsert_task(investigation_id, name, "unavailable")

    async def mark_agent_finished(
        self,
        investigation_id: str,
        agent: str,
        *,
        status: str,
        findings_count: int = 0,
        error: str | None = None,
    ) -> None:
        mapped = "failed" if status in {"failed", "data_unavailable"} else status
        if mapped not in {"completed", "failed", "partial"}:
            mapped = "completed" if status == "completed" else "failed"
        await self._store.upsert_task(
            investigation_id,
            agent,
            mapped,
            findings_count=findings_count,
            error=error,
        )

    async def record_iteration(
        self,
        investigation_id: str,
        research_iteration: int,
    ) -> None:
        await self._store.update_public_fields(
            investigation_id,
            research_iteration=research_iteration,
        )
