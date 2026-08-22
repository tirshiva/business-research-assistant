"""Evidence repository abstraction and in-memory implementation."""

from __future__ import annotations

from typing import Protocol

from app.evidence.models import Contradiction, Evidence


class EvidenceRepository(Protocol):
    """Persistence contract for evidence and contradictions.

    In-memory for MVP; a PostgreSQL implementation can satisfy the same
    protocol later without changing call sites.
    """

    async def add(self, evidence: Evidence) -> Evidence:
        """Persist an evidence item and return the stored copy."""

    async def get(self, evidence_id: str) -> Evidence | None:
        """Fetch a single evidence item by id."""

    async def list_by_investigation(self, investigation_id: str) -> list[Evidence]:
        """Return all evidence for an investigation."""

    async def find_by_claim(
        self,
        investigation_id: str,
        claim: str,
    ) -> list[Evidence]:
        """Return evidence matching a claim within an investigation."""

    async def add_contradiction(self, contradiction: Contradiction) -> Contradiction:
        """Persist an explicit contradiction record."""

    async def list_contradictions(self, investigation_id: str) -> list[Contradiction]:
        """Return contradictions for an investigation."""

    async def delete(self, evidence_id: str) -> bool:
        """Delete an evidence item. Returns True if it existed."""

    async def clear(self) -> None:
        """Remove all evidence and contradictions (test / reset helper)."""


class InMemoryEvidenceRepository:
    """Process-local evidence store suitable for local development and tests."""

    def __init__(self) -> None:
        self._evidence: dict[str, Evidence] = {}
        self._contradictions: dict[str, Contradiction] = {}

    async def add(self, evidence: Evidence) -> Evidence:
        stored = evidence.model_copy(deep=True)
        self._evidence[stored.evidence_id] = stored
        return stored.model_copy(deep=True)

    async def get(self, evidence_id: str) -> Evidence | None:
        item = self._evidence.get(evidence_id)
        return item.model_copy(deep=True) if item else None

    async def list_by_investigation(self, investigation_id: str) -> list[Evidence]:
        items = [
            item.model_copy(deep=True)
            for item in self._evidence.values()
            if item.investigation_id == investigation_id
        ]
        items.sort(key=lambda item: item.retrieved_at)
        return items

    async def find_by_claim(
        self,
        investigation_id: str,
        claim: str,
    ) -> list[Evidence]:
        key = " ".join(claim.lower().split())
        items = [
            item.model_copy(deep=True)
            for item in self._evidence.values()
            if item.investigation_id == investigation_id
            and item.normalized_claim == key
        ]
        items.sort(key=lambda item: item.retrieved_at)
        return items

    async def add_contradiction(self, contradiction: Contradiction) -> Contradiction:
        stored = contradiction.model_copy(deep=True)
        self._contradictions[stored.contradiction_id] = stored
        return stored.model_copy(deep=True)

    async def list_contradictions(self, investigation_id: str) -> list[Contradiction]:
        items = [
            item.model_copy(deep=True)
            for item in self._contradictions.values()
            if item.investigation_id == investigation_id
        ]
        items.sort(key=lambda item: item.detected_at)
        return items

    async def delete(self, evidence_id: str) -> bool:
        return self._evidence.pop(evidence_id, None) is not None

    async def clear(self) -> None:
        self._evidence.clear()
        self._contradictions.clear()
