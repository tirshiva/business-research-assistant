"""SQLAlchemy table models for investigations and related records."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

LifecycleStatus = (
    "CREATED",
    "PLANNING",
    "RESEARCHING",
    "VALIDATING",
    "ANALYZING",
    "REVIEWING",
    "COMPLETED",
    "FAILED",
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class InvestigationRow(Base):
    """Top-level investigation record."""

    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CREATED")
    business_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(512), nullable=True)
    objective: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_customer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    budget: Mapped[str | None] = mapped_column(String(128), nullable=True)
    plan: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    scores: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    insights: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    critic_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_iteration: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )

    tasks: Mapped[list[ResearchTaskRow]] = relationship(
        back_populates="investigation",
        cascade="all, delete-orphan",
    )
    evidence: Mapped[list[EvidenceRow]] = relationship(
        back_populates="investigation",
        cascade="all, delete-orphan",
    )
    contradictions: Mapped[list[ContradictionRow]] = relationship(
        back_populates="investigation",
        cascade="all, delete-orphan",
    )
    recommendations: Mapped[list[RecommendationRow]] = relationship(
        back_populates="investigation",
        cascade="all, delete-orphan",
    )


class ResearchTaskRow(Base):
    """A planned or executed research task."""

    __tablename__ = "research_tasks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    investigation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    investigation: Mapped[InvestigationRow] = relationship(back_populates="tasks")


class EvidenceRow(Base):
    """Persisted evidence item."""

    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent: Mapped[str] = mapped_column(String(64), nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=True)
    claim_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="FACT")
    source: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    investigation: Mapped[InvestigationRow] = relationship(back_populates="evidence")


class ContradictionRow(Base):
    """Persisted contradiction between evidence items."""

    __tablename__ = "contradictions"

    contradiction_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    values: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    investigation: Mapped[InvestigationRow] = relationship(
        back_populates="contradictions"
    )


class RecommendationRow(Base):
    """Persisted recommendation snapshot for an investigation."""

    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    investigation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    critic_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    investigation: Mapped[InvestigationRow] = relationship(
        back_populates="recommendations"
    )
