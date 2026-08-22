"""Evidence collection node — merge agent findings into investigation state."""

from __future__ import annotations

from typing import Any

from app.agents.schemas import AgentResult
from app.core.exceptions import EvidenceValidationError
from app.core.logging import get_logger
from app.graph.deps import ResearchOrchestrationDeps
from app.graph.progress import emit_progress
from app.graph.state import InvestigationState

logger = get_logger(__name__)


def create_evidence_collection_node(deps: ResearchOrchestrationDeps):
    """Build the evidence collection / merge node."""

    async def evidence_collection(state: InvestigationState) -> dict[str, Any]:
        iteration = int(state.get("iteration") or 0) + 1
        research_iteration = int(state.get("research_iteration") or 0) + 1
        investigation_id = state["investigation_id"]
        agent_results = list(state.get("agent_results") or [])
        unavailable = list(state.get("unavailable_dimensions") or [])
        metadata = dict(state.get("metadata") or {})
        errors = list(state.get("validation_errors") or [])

        existing_evidence = list(state.get("evidence") or [])
        evidence_items: list[dict[str, Any]] = []
        contradiction_summaries: list[str] = list(state.get("contradictions") or [])
        submitted = 0
        successful_agents = 0
        failed_or_unavailable = 0

        for raw in agent_results:
            try:
                result = AgentResult.model_validate(raw)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"invalid_agent_result: {exc}")
                failed_or_unavailable += 1
                continue

            if result.status == "completed":
                successful_agents += 1
            else:
                failed_or_unavailable += 1
                if result.agent not in unavailable:
                    unavailable.append(result.agent)

            if not result.findings:
                continue

            if result.agent in {
                item.get("agent") for item in existing_evidence if item.get("agent")
            }:
                continue

            try:
                stored = await deps.evidence_service.submit_agent_result(
                    investigation_id=investigation_id,
                    result=result,
                    claim_kind="FACT",
                )
                submitted += len(stored)
                evidence_items.extend(item.model_dump(mode="json") for item in stored)
            except EvidenceValidationError as exc:
                duplicate_only = bool(exc.issues) and all(
                    issue.get("code") == "duplicate_evidence" for issue in exc.issues
                )
                if duplicate_only:
                    logger.info(
                        "Skipping duplicate evidence id=%s agent=%s",
                        investigation_id,
                        result.agent,
                    )
                    continue
                errors.append(
                    f"evidence_validation_failed:{result.agent}:{exc.message}"
                )
                logger.warning(
                    "Evidence validation failed id=%s agent=%s issues=%s",
                    investigation_id,
                    result.agent,
                    exc.issues,
                )

        merged: dict[str, dict[str, Any]] = {}
        orphans: list[dict[str, Any]] = []
        for item in [*existing_evidence, *evidence_items]:
            key = str(item.get("evidence_id") or "")
            if key:
                merged[key] = item
            else:
                orphans.append(item)
        evidence_items = [*merged.values(), *orphans]

        # Pull any repository contradictions for this investigation.
        repo_contradictions = await deps.evidence_service.list_contradictions(
            investigation_id
        )
        for item in repo_contradictions:
            if item.summary not in contradiction_summaries:
                contradiction_summaries.append(item.summary)

        confidence = None
        if evidence_items:
            from app.evidence.models import Evidence

            models = [Evidence.model_validate(item) for item in evidence_items]
            confidence = deps.evidence_service.aggregate_confidence(models)

        if state.get("status") == "failed":
            final_status = "failed"
        else:
            has_partial = bool(
                (failed_or_unavailable and successful_agents)
                or (failed_or_unavailable and agent_results)
                or (not agent_results and unavailable)
            )
            final_status = "partial" if has_partial else "completed"

        analysis = (
            f"Research complete: {successful_agents} agent(s) succeeded, "
            f"{failed_or_unavailable} failed/unavailable, "
            f"{submitted} evidence item(s) stored."
        )
        metadata["evidence_collection"] = {
            "submitted_evidence": submitted,
            "successful_agents": successful_agents,
            "failed_or_unavailable": failed_or_unavailable,
            "agent_runs": state.get("agent_runs") or [],
        }

        logger.info(
            "Evidence collection id=%s status=%s evidence=%s unavailable=%s",
            investigation_id,
            final_status,
            submitted,
            unavailable,
        )

        await emit_progress(deps, "mark_stage", investigation_id, "VALIDATING")
        await emit_progress(
            deps,
            "record_iteration",
            investigation_id,
            research_iteration,
        )

        return {
            "evidence": evidence_items,
            "contradictions": contradiction_summaries,
            "unavailable_dimensions": unavailable,
            "confidence": confidence,
            "analysis": analysis,
            "validation_errors": errors,
            "status": final_status,
            "iteration": iteration,
            "research_iteration": research_iteration,
            "metadata": metadata,
        }

    return evidence_collection
