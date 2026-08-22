"""Application service that runs investigations and persists public results."""

from __future__ import annotations

from typing import Any

from app.api.schemas import (
    CriticSummary,
    EvidenceItemResponse,
    EvidenceListResponse,
    InvestigationReportResponse,
    InvestigationResponse,
    InvestigationStatusResponse,
    ResearchTaskResponse,
    ScoreSummary,
)
from app.core.exceptions import InvestigationConflictError, InvestigationNotFoundError
from app.core.logging import get_logger
from app.db.models import EvidenceRow, InvestigationRow
from app.db.store import InvestigationStore
from app.models.investigation import InvestigationRequest
from app.services.investigation import InvestigationService

logger = get_logger(__name__)

_IN_FLIGHT = {
    "PLANNING",
    "RESEARCHING",
    "VALIDATING",
    "ANALYZING",
    "REVIEWING",
}


class InvestigationAppService:
    """Orchestrate create / run / read without leaking LangGraph state."""

    def __init__(
        self,
        store: InvestigationStore,
        runner: InvestigationService,
    ) -> None:
        self._store = store
        self._runner = runner
        self._running: set[str] = set()

    async def create(self, query: str) -> tuple[str, str]:
        """Persist a CREATED investigation and return ``(id, status)``."""
        investigation_id = await self._store.create(query)
        return investigation_id, "CREATED"

    async def run_background(self, investigation_id: str) -> None:
        """Execute research and persist outputs. Safe to schedule as a task."""
        try:
            await self._execute(investigation_id)
        except Exception:
            logger.exception(
                "Investigation execution failed id=%s",
                investigation_id,
            )
            try:
                await self._store.set_status(
                    investigation_id,
                    "FAILED",
                    error_message="Investigation failed due to an unexpected error",
                )
            except InvestigationNotFoundError:
                return

    async def request_additional_research(
        self,
        investigation_id: str,
        tasks: list[str] | None = None,
    ) -> tuple[str, str]:
        """Queue another research pass for an existing investigation."""
        row = await self._store.get(investigation_id)
        if row.status in _IN_FLIGHT or investigation_id in self._running:
            raise InvestigationConflictError(
                "Investigation is already running",
                investigation_id=investigation_id,
            )
        del tasks  # Follow-up runs the full graph; critic required_research applies.
        return investigation_id, row.status

    async def get_investigation(self, investigation_id: str) -> InvestigationResponse:
        row = await self._store.get(investigation_id)
        return _to_investigation_response(row)

    async def get_status(self, investigation_id: str) -> InvestigationStatusResponse:
        row = await self._store.get(investigation_id)
        return InvestigationStatusResponse(
            id=row.id,
            status=row.status,  # type: ignore[arg-type]
            created_at=row.created_at,
            updated_at=row.updated_at,
            error=row.error_message,
        )

    async def get_evidence(self, investigation_id: str) -> EvidenceListResponse:
        items = await self._store.list_evidence(investigation_id)
        return EvidenceListResponse(
            investigation_id=investigation_id,
            items=[_to_evidence_item(item) for item in items],
        )

    async def get_report(self, investigation_id: str) -> InvestigationReportResponse:
        row = await self._store.get(investigation_id)
        return _to_report(row)

    async def _execute(self, investigation_id: str) -> None:
        if investigation_id in self._running:
            raise InvestigationConflictError(
                "Investigation is already running",
                investigation_id=investigation_id,
            )
        self._running.add(investigation_id)
        try:
            row = await self._store.get(investigation_id)
            await self._store.set_status(investigation_id, "PLANNING")
            await self._store.set_status(investigation_id, "RESEARCHING")
            result = await self._runner.run(
                InvestigationRequest(user_query=row.query),
                investigation_id=investigation_id,
            )
            if result.status == "failed":
                await self._store.set_status(
                    investigation_id,
                    "FAILED",
                    error_message="; ".join(result.validation_errors)
                    or "Investigation graph failed",
                )
                await self._store.save_result(result, lifecycle="FAILED")
                return

            await self._store.set_status(investigation_id, "VALIDATING")
            await self._store.set_status(investigation_id, "ANALYZING")
            await self._store.set_status(investigation_id, "REVIEWING")
            await self._store.save_result(result, lifecycle="COMPLETED")
        finally:
            self._running.discard(investigation_id)


def _to_investigation_response(row: InvestigationRow) -> InvestigationResponse:
    return InvestigationResponse(
        id=row.id,
        query=row.query,
        status=row.status,  # type: ignore[arg-type]
        business_type=row.business_type,
        location=row.location,
        objective=row.objective,
        target_customer=row.target_customer,
        plan=list(row.plan or []),
        tasks=[
            ResearchTaskResponse(
                task_type=task.task_type,
                status=task.status,
                findings_count=task.findings_count,
                error=task.error,
            )
            for task in sorted(row.tasks, key=lambda item: item.task_type)
        ],
        opportunity_score=row.opportunity_score,
        recommendation=row.recommendation_label,
        confidence=row.confidence,
        critic=_critic_summary(row.critic_result),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_report(row: InvestigationRow) -> InvestigationReportResponse:
    scores = None
    raw_scores = row.scores if isinstance(row.scores, dict) else None
    if raw_scores is not None or row.opportunity_score is not None:
        scores = ScoreSummary(
            overall_score=row.opportunity_score
            if row.opportunity_score is not None
            else raw_scores.get("overall_score")
            if raw_scores
            else None,
            recommendation=row.recommendation_label,
            dimensions=list((raw_scores or {}).get("dimensions") or []),
        )
    return InvestigationReportResponse(
        investigation_id=row.id,
        query=row.query,
        status=row.status,  # type: ignore[arg-type]
        location=row.location,
        business_type=row.business_type,
        plan=list(row.plan or []),
        scores=scores,
        recommendation=row.recommendation_label,
        critic=_critic_summary(row.critic_result),
        report=row.report or "",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _critic_summary(payload: dict[str, Any] | None) -> CriticSummary | None:
    if not payload:
        return None
    return CriticSummary(
        status=payload.get("status"),
        confidence=payload.get("confidence"),
        issues=list(payload.get("issues") or []),
        required_research=list(payload.get("required_research") or []),
    )


def _to_evidence_item(row: EvidenceRow) -> EvidenceItemResponse:
    source = row.source if isinstance(row.source, dict) else {}
    return EvidenceItemResponse(
        evidence_id=row.evidence_id,
        agent=row.agent,
        claim=row.claim,
        value=row.value,
        claim_kind=row.claim_kind,
        source_name=source.get("name"),
        source_url=row.source_url or source.get("url"),
        retrieved_at=row.retrieved_at,
        confidence=row.confidence,
    )
