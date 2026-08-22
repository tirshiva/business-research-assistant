"""Evidence validation and contradiction detection."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.evidence.models import (
    Contradiction,
    Evidence,
    EvidenceValidationResult,
    ValidationIssue,
)


class EvidenceValidator:
    """Validate evidence integrity and detect duplicates / contradictions."""

    def __init__(
        self,
        *,
        min_confidence: float = 0.3,
        stale_after_hours: float = 72.0,
        treat_low_confidence_as_error: bool = False,
    ) -> None:
        self._min_confidence = min_confidence
        self._stale_after = timedelta(hours=stale_after_hours)
        self._low_confidence_as_error = treat_low_confidence_as_error

    def validate(
        self,
        evidence: Evidence,
        *,
        existing: list[Evidence] | None = None,
        now: datetime | None = None,
    ) -> EvidenceValidationResult:
        """Validate a single evidence item against optional existing corpus."""
        issues: list[ValidationIssue] = []
        contradictions: list[Contradiction] = []
        current_time = now or datetime.now(UTC)

        issues.extend(self._check_source(evidence))
        issues.extend(self._check_timestamp(evidence))
        issues.extend(self._check_confidence(evidence))
        issues.extend(self._check_stale(evidence, now=current_time))
        issues.extend(self._check_claim_kind(evidence))

        corpus = list(existing or [])
        duplicate = self._find_duplicate(evidence, corpus)
        if duplicate is not None:
            issues.append(
                ValidationIssue(
                    code="duplicate_evidence",
                    message=(
                        f"Duplicate of evidence_id={duplicate.evidence_id} "
                        f"for claim '{evidence.claim}'"
                    ),
                    severity="error",
                    evidence_id=evidence.evidence_id,
                )
            )

        contradiction = self._detect_contradiction(evidence, corpus)
        if contradiction is not None:
            contradictions.append(contradiction)
            issues.append(
                ValidationIssue(
                    code="contradictory_evidence",
                    message=contradiction.summary,
                    severity="error",
                    evidence_id=evidence.evidence_id,
                )
            )

        # Cleaner validate() blocking logic — rewrite the messy part
        blocking_codes = {
            "missing_source",
            "missing_timestamp",
            "duplicate_evidence",
            "invalid_claim_kind",
        }
        if self._low_confidence_as_error:
            blocking_codes.add("low_confidence")

        is_valid = not any(
            issue.code in blocking_codes and issue.severity == "error"
            for issue in issues
        )

        return EvidenceValidationResult(
            is_valid=is_valid,
            issues=issues,
            contradictions=contradictions,
        )

    def detect_contradictions(
        self,
        evidence_items: list[Evidence],
    ) -> list[Contradiction]:
        """Scan a corpus and emit all FACT claim contradictions."""
        by_claim: dict[str, list[Evidence]] = {}
        for item in evidence_items:
            if item.claim_kind != "FACT":
                continue
            by_claim.setdefault(item.normalized_claim, []).append(item)

        contradictions: list[Contradiction] = []
        for claim_key, items in by_claim.items():
            unique_values = _unique_values([item.value for item in items])
            if len(unique_values) < 2:
                continue
            contradictions.append(
                Contradiction(
                    investigation_id=items[0].investigation_id,
                    claim=items[0].claim,
                    evidence_ids=[item.evidence_id for item in items],
                    values=unique_values,
                    summary=(
                        f"Contradictory FACT values for claim '{claim_key}': "
                        f"{unique_values}"
                    ),
                    metadata={"claim_key": claim_key},
                )
            )
        return contradictions

    def aggregate_confidence(self, evidence_items: list[Evidence]) -> float:
        """Compute a provenance-weighted confidence score for a claim set.

        FACT evidence is weighted higher than INFERENCE. RECOMMENDATION items
        do not contribute (they are not evidentiary support for facts).
        """
        weighted: list[tuple[float, float]] = []
        for item in evidence_items:
            if item.claim_kind == "RECOMMENDATION":
                continue
            weight = 1.0 if item.claim_kind == "FACT" else 0.6
            reliability_boost = {
                "high": 1.0,
                "medium": 0.85,
                "low": 0.6,
                "unknown": 0.75,
            }.get(item.source.reliability, 0.75)
            weighted.append((item.confidence * reliability_boost, weight))

        if not weighted:
            return 0.0
        total_weight = sum(weight for _, weight in weighted)
        score = sum(value * weight for value, weight in weighted) / total_weight
        return round(min(1.0, max(0.0, score)), 4)

    def _check_source(self, evidence: Evidence) -> list[ValidationIssue]:
        if evidence.source is None or not evidence.source.name.strip():
            return [
                ValidationIssue(
                    code="missing_source",
                    message="Evidence is missing a source name",
                    severity="error",
                    evidence_id=evidence.evidence_id,
                )
            ]
        return []

    def _check_timestamp(self, evidence: Evidence) -> list[ValidationIssue]:
        if evidence.retrieved_at is None:
            return [
                ValidationIssue(
                    code="missing_timestamp",
                    message="Evidence is missing retrieved_at",
                    severity="error",
                    evidence_id=evidence.evidence_id,
                )
            ]
        return []

    def _check_confidence(self, evidence: Evidence) -> list[ValidationIssue]:
        if evidence.confidence < self._min_confidence:
            severity = "error" if self._low_confidence_as_error else "warning"
            return [
                ValidationIssue(
                    code="low_confidence",
                    message=(
                        f"Confidence {evidence.confidence} is below "
                        f"threshold {self._min_confidence}"
                    ),
                    severity=severity,
                    evidence_id=evidence.evidence_id,
                )
            ]
        return []

    def _check_stale(
        self,
        evidence: Evidence,
        *,
        now: datetime,
    ) -> list[ValidationIssue]:
        retrieved = evidence.retrieved_at
        if retrieved.tzinfo is None:
            retrieved = retrieved.replace(tzinfo=UTC)
        current = now if now.tzinfo else now.replace(tzinfo=UTC)
        if current - retrieved > self._stale_after:
            return [
                ValidationIssue(
                    code="stale_data",
                    message=(
                        "Evidence is older than "
                        f"{self._stale_after.total_seconds() / 3600:.1f} hours"
                    ),
                    severity="warning",
                    evidence_id=evidence.evidence_id,
                )
            ]
        return []

    def _check_claim_kind(self, evidence: Evidence) -> list[ValidationIssue]:
        if evidence.claim_kind not in {"FACT", "INFERENCE", "RECOMMENDATION"}:
            return [
                ValidationIssue(
                    code="invalid_claim_kind",
                    message=f"Unsupported claim_kind={evidence.claim_kind}",
                    severity="error",
                    evidence_id=evidence.evidence_id,
                )
            ]
        return []

    def _find_duplicate(
        self,
        evidence: Evidence,
        existing: list[Evidence],
    ) -> Evidence | None:
        fingerprint = _evidence_fingerprint(evidence)
        for item in existing:
            if item.evidence_id == evidence.evidence_id:
                continue
            if (
                item.investigation_id == evidence.investigation_id
                and item.agent == evidence.agent
                and _evidence_fingerprint(item) == fingerprint
            ):
                return item
        return None

    def _detect_contradiction(
        self,
        evidence: Evidence,
        existing: list[Evidence],
    ) -> Contradiction | None:
        if evidence.claim_kind != "FACT":
            return None
        peers = [
            item
            for item in existing
            if item.investigation_id == evidence.investigation_id
            and item.claim_kind == "FACT"
            and item.normalized_claim == evidence.normalized_claim
            and item.evidence_id != evidence.evidence_id
        ]
        conflicting = [
            item for item in peers if not _values_equal(item.value, evidence.value)
        ]
        if not conflicting:
            return None
        involved = [*conflicting, evidence]
        values = _unique_values([item.value for item in involved])
        return Contradiction(
            investigation_id=evidence.investigation_id,
            claim=evidence.claim,
            evidence_ids=[item.evidence_id for item in involved],
            values=values,
            summary=(
                f"Contradictory FACT values for claim '{evidence.normalized_claim}': "
                f"{values}"
            ),
            metadata={"claim_key": evidence.normalized_claim},
        )


def _evidence_fingerprint(evidence: Evidence) -> str:
    return "|".join(
        [
            evidence.normalized_claim,
            _stable_dumps(evidence.value),
            evidence.claim_kind,
            (evidence.source_url or evidence.source.url or "").strip().lower(),
        ]
    )


def _stable_dumps(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return repr(value)


def _values_equal(left: Any, right: Any) -> bool:
    return _stable_dumps(left) == _stable_dumps(right)


def _unique_values(values: list[Any]) -> list[Any]:
    unique: list[Any] = []
    seen: set[str] = set()
    for value in values:
        key = _stable_dumps(value)
        if key in seen:
            continue
        seen.add(key)
        unique.append(value)
    return unique
