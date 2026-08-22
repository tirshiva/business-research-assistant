"""Persistence helpers mapping domain models to SQLAlchemy rows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.exceptions import InvestigationNotFoundError
from app.db.models import (
    ContradictionRow,
    EvidenceRow,
    InvestigationRow,
    RecommendationRow,
    ResearchTaskRow,
)
from app.evidence.models import Contradiction, Evidence, SourceRecord
from app.models.investigation import InvestigationResult


def _utcnow() -> datetime:
    return datetime.now(UTC)


class InvestigationStore:
    """Create, update, and load investigations without exposing graph state."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def create(
        self,
        query: str,
        *,
        investigation_id: str | None = None,
        business_type: str | None = None,
        location: str | None = None,
        target_customer: str | None = None,
        budget: str | None = None,
    ) -> str:
        """Insert a CREATED investigation and return its id."""
        async with self._sessions() as session:
            row = InvestigationRow(
                query=query,
                status="CREATED",
                business_type=business_type,
                location=location,
                target_customer=target_customer,
                budget=budget,
            )
            if investigation_id:
                row.id = investigation_id
            session.add(row)
            await session.commit()
            return row.id

    async def get(self, investigation_id: str) -> InvestigationRow:
        """Load an investigation with related collections."""
        async with self._sessions() as session:
            row = await self._load(session, investigation_id)
            if row is None:
                raise InvestigationNotFoundError(investigation_id)
            await session.refresh(row)
            return row

    async def exists(self, investigation_id: str) -> bool:
        async with self._sessions() as session:
            row = await session.get(InvestigationRow, investigation_id)
            return row is not None

    async def set_status(
        self,
        investigation_id: str,
        status: str,
        *,
        error_message: str | None = None,
    ) -> None:
        async with self._sessions() as session:
            row = await session.get(InvestigationRow, investigation_id)
            if row is None:
                raise InvestigationNotFoundError(investigation_id)
            row.status = status
            row.updated_at = _utcnow()
            if error_message is not None:
                row.error_message = error_message
            await session.commit()

    async def save_result(self, result: InvestigationResult, *, lifecycle: str) -> None:
        """Persist graph outputs into public investigation tables."""
        async with self._sessions() as session:
            row = await self._load(session, result.investigation_id)
            if row is None:
                raise InvestigationNotFoundError(result.investigation_id)

            row.status = lifecycle
            row.business_type = result.business_type
            row.location = result.location
            row.objective = result.objective
            row.target_customer = result.target_customer
            row.plan = list(result.research_plan)
            row.scores = (result.metadata or {}).get("opportunity_scorecard")
            insights = (result.metadata or {}).get("analysis")
            row.insights = insights if isinstance(insights, dict) else None
            row.opportunity_score = result.opportunity_score
            row.recommendation_label = result.recommendation
            row.confidence = result.confidence
            row.critic_result = _critic_payload(result)
            row.report = _compose_report(result)
            row.research_iteration = result.research_iteration
            errors = result.validation_errors
            row.error_message = "; ".join(errors) if errors else None
            row.updated_at = _utcnow()

            await session.execute(
                delete(ResearchTaskRow).where(
                    ResearchTaskRow.investigation_id == row.id
                )
            )
            for task in _tasks_from_result(result):
                session.add(task)

            await _upsert_evidence(session, result)

            await session.execute(
                delete(RecommendationRow).where(
                    RecommendationRow.investigation_id == row.id
                )
            )
            if result.recommendation:
                session.add(
                    RecommendationRow(
                        investigation_id=row.id,
                        label=result.recommendation,
                        score=result.opportunity_score,
                        confidence=result.confidence,
                        critic_status=result.critic_status,
                        summary=result.analysis,
                    )
                )
            await session.commit()

    async def update_public_fields(
        self,
        investigation_id: str,
        *,
        status: str | None = None,
        plan: list[str] | None = None,
        business_type: str | None = None,
        location: str | None = None,
        target_customer: str | None = None,
        research_iteration: int | None = None,
    ) -> None:
        async with self._sessions() as session:
            row = await session.get(InvestigationRow, investigation_id)
            if row is None:
                raise InvestigationNotFoundError(investigation_id)
            if status is not None:
                row.status = status
            if plan is not None:
                row.plan = plan
            if business_type is not None:
                row.business_type = business_type
            if location is not None:
                row.location = location
            if target_customer is not None:
                row.target_customer = target_customer
            if research_iteration is not None:
                row.research_iteration = research_iteration
            row.updated_at = _utcnow()
            await session.commit()

    async def replace_tasks(
        self,
        investigation_id: str,
        tasks: list[tuple[str, str]],
    ) -> None:
        async with self._sessions() as session:
            if await session.get(InvestigationRow, investigation_id) is None:
                raise InvestigationNotFoundError(investigation_id)
            await session.execute(
                delete(ResearchTaskRow).where(
                    ResearchTaskRow.investigation_id == investigation_id
                )
            )
            for name, status in tasks:
                session.add(
                    ResearchTaskRow(
                        investigation_id=investigation_id,
                        task_type=name,
                        status=status,
                    )
                )
            await session.commit()

    async def upsert_task(
        self,
        investigation_id: str,
        task_type: str,
        status: str,
        *,
        findings_count: int = 0,
        error: str | None = None,
    ) -> None:
        async with self._sessions() as session:
            result = await session.scalars(
                select(ResearchTaskRow).where(
                    ResearchTaskRow.investigation_id == investigation_id,
                    ResearchTaskRow.task_type == task_type,
                )
            )
            row = result.first()
            if row is None:
                session.add(
                    ResearchTaskRow(
                        investigation_id=investigation_id,
                        task_type=task_type,
                        status=status,
                        findings_count=findings_count,
                        error=error,
                    )
                )
            else:
                row.status = status
                row.findings_count = findings_count
                row.error = error
            await session.commit()

    async def evidence_count(self, investigation_id: str) -> int:
        async with self._sessions() as session:
            result = await session.scalars(
                select(EvidenceRow.evidence_id).where(
                    EvidenceRow.investigation_id == investigation_id
                )
            )
            return len(list(result.all()))

    async def list_evidence(self, investigation_id: str) -> list[EvidenceRow]:
        async with self._sessions() as session:
            if await session.get(InvestigationRow, investigation_id) is None:
                raise InvestigationNotFoundError(investigation_id)
            result = await session.scalars(
                select(EvidenceRow)
                .where(EvidenceRow.investigation_id == investigation_id)
                .order_by(EvidenceRow.retrieved_at)
            )
            return list(result.all())

    async def _load(
        self,
        session: AsyncSession,
        investigation_id: str,
    ) -> InvestigationRow | None:
        result = await session.scalars(
            select(InvestigationRow)
            .options(
                selectinload(InvestigationRow.tasks),
                selectinload(InvestigationRow.evidence),
                selectinload(InvestigationRow.contradictions),
                selectinload(InvestigationRow.recommendations),
            )
            .where(InvestigationRow.id == investigation_id)
        )
        return result.one_or_none()


class SqlAlchemyEvidenceRepository:
    """EvidenceRepository backed by the evidence / contradictions tables."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def add(self, evidence: Evidence) -> Evidence:
        async with self._sessions() as session:
            session.add(_evidence_to_row(evidence))
            await session.commit()
            return evidence.model_copy(deep=True)

    async def get(self, evidence_id: str) -> Evidence | None:
        async with self._sessions() as session:
            row = await session.get(EvidenceRow, evidence_id)
            return _row_to_evidence(row) if row else None

    async def list_by_investigation(self, investigation_id: str) -> list[Evidence]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(EvidenceRow)
                .where(EvidenceRow.investigation_id == investigation_id)
                .order_by(EvidenceRow.retrieved_at)
            )
            return [_row_to_evidence(row) for row in result.all()]

    async def find_by_claim(
        self,
        investigation_id: str,
        claim: str,
    ) -> list[Evidence]:
        key = " ".join(claim.lower().split())
        items = await self.list_by_investigation(investigation_id)
        return [item for item in items if item.normalized_claim == key]

    async def add_contradiction(self, contradiction: Contradiction) -> Contradiction:
        async with self._sessions() as session:
            session.add(_contradiction_to_row(contradiction))
            await session.commit()
            return contradiction.model_copy(deep=True)

    async def list_contradictions(self, investigation_id: str) -> list[Contradiction]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(ContradictionRow)
                .where(ContradictionRow.investigation_id == investigation_id)
                .order_by(ContradictionRow.detected_at)
            )
            return [_row_to_contradiction(row) for row in result.all()]

    async def delete(self, evidence_id: str) -> bool:
        async with self._sessions() as session:
            row = await session.get(EvidenceRow, evidence_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def clear(self) -> None:
        async with self._sessions() as session:
            await session.execute(delete(ContradictionRow))
            await session.execute(delete(EvidenceRow))
            await session.commit()


def _critic_payload(result: InvestigationResult) -> dict[str, Any]:
    stored = (result.metadata or {}).get("critic")
    if isinstance(stored, dict):
        return stored
    return {
        "status": result.critic_status,
        "confidence": result.critic_confidence,
        "issues": list(result.critic_issues),
        "required_research": list(result.required_research),
    }


def _compose_report(result: InvestigationResult) -> str:
    lines = [
        f"Query: {result.user_query}",
        f"Recommendation: {result.recommendation or 'n/a'}",
        (
            f"Opportunity score: {result.opportunity_score:.2f}/10"
            if result.opportunity_score is not None
            else "Opportunity score: n/a"
        ),
        f"Critic: {result.critic_status or 'n/a'}",
        "",
        result.analysis or "No analysis text was produced.",
    ]
    return "\n".join(lines)


def _tasks_from_result(result: InvestigationResult) -> list[ResearchTaskRow]:
    runs_by_agent = {
        run.get("agent"): run for run in result.agent_runs if run.get("agent")
    }
    unavailable = set(result.unavailable_dimensions or [])
    tasks: list[ResearchTaskRow] = []
    seen: set[str] = set()
    for name in result.research_plan:
        seen.add(name)
        run = runs_by_agent.get(name)
        if run:
            status = str(run.get("status") or "completed")
            if status == "data_unavailable":
                status = "failed"
            tasks.append(
                ResearchTaskRow(
                    investigation_id=result.investigation_id,
                    task_type=name,
                    status=status,
                    error=run.get("error"),
                    findings_count=int(run.get("findings_count") or 0),
                )
            )
        elif name in unavailable:
            tasks.append(
                ResearchTaskRow(
                    investigation_id=result.investigation_id,
                    task_type=name,
                    status="unavailable",
                )
            )
        else:
            tasks.append(
                ResearchTaskRow(
                    investigation_id=result.investigation_id,
                    task_type=name,
                    status="pending",
                )
            )
    for agent, run in runs_by_agent.items():
        if agent in seen:
            continue
        tasks.append(
            ResearchTaskRow(
                investigation_id=result.investigation_id,
                task_type=str(agent),
                status=str(run.get("status") or "completed"),
                error=run.get("error"),
                findings_count=int(run.get("findings_count") or 0),
            )
        )
    return tasks


async def _upsert_evidence(session: AsyncSession, result: InvestigationResult) -> None:
    for raw in result.evidence:
        try:
            item = Evidence.model_validate(raw)
        except Exception:  # noqa: BLE001
            continue
        existing = await session.get(EvidenceRow, item.evidence_id)
        row = _evidence_to_row(item)
        if existing is None:
            session.add(row)
        else:
            existing.agent = row.agent
            existing.claim = row.claim
            existing.value = row.value
            existing.claim_kind = row.claim_kind
            existing.source = row.source
            existing.source_url = row.source_url
            existing.retrieved_at = row.retrieved_at
            existing.confidence = row.confidence
            existing.extra = row.extra


def _evidence_to_row(item: Evidence) -> EvidenceRow:
    return EvidenceRow(
        evidence_id=item.evidence_id,
        investigation_id=item.investigation_id,
        agent=item.agent,
        claim=item.claim,
        value=item.value,
        claim_kind=item.claim_kind,
        source=item.source.model_dump(mode="json"),
        source_url=item.source_url,
        retrieved_at=item.retrieved_at,
        confidence=item.confidence,
        extra=item.metadata,
    )


def _row_to_evidence(row: EvidenceRow) -> Evidence:
    return Evidence(
        evidence_id=row.evidence_id,
        investigation_id=row.investigation_id,
        agent=row.agent,
        claim=row.claim,
        value=row.value,
        claim_kind=row.claim_kind,  # type: ignore[arg-type]
        source=SourceRecord.model_validate(row.source),
        source_url=row.source_url,
        retrieved_at=row.retrieved_at,
        confidence=row.confidence,
        metadata=row.extra or {},
    )


def _contradiction_to_row(item: Contradiction) -> ContradictionRow:
    return ContradictionRow(
        contradiction_id=item.contradiction_id,
        investigation_id=item.investigation_id,
        claim=item.claim,
        evidence_ids=list(item.evidence_ids),
        values=list(item.values),
        summary=item.summary,
        detected_at=item.detected_at,
        extra=item.metadata,
    )


def _row_to_contradiction(row: ContradictionRow) -> Contradiction:
    return Contradiction(
        contradiction_id=row.contradiction_id,
        investigation_id=row.investigation_id,
        claim=row.claim,
        evidence_ids=list(row.evidence_ids or []),
        values=list(row.values or []),
        summary=row.summary,
        detected_at=row.detected_at,
        metadata=row.extra or {},
    )
