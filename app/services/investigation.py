"""Service for executing the investigation LangGraph."""

from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph
from pydantic import ValidationError

from app.config import get_settings
from app.core.exceptions import InvestigationInputError
from app.core.logging import get_logger
from app.graph.graph import get_investigation_graph
from app.graph.state import InvestigationState, create_initial_state
from app.models.investigation import InvestigationRequest, InvestigationResult

logger = get_logger(__name__)


class InvestigationService:
    """Accept a user query, run the investigation graph, and return final state."""

    def __init__(self, graph: CompiledStateGraph | None = None) -> None:
        self._graph = graph or get_investigation_graph()

    async def run(
        self,
        payload: InvestigationRequest | dict[str, str],
        *,
        investigation_id: str | None = None,
    ) -> InvestigationResult:
        """Execute the multi-agent investigation graph and return validated state."""
        request = self._validate_request(payload)
        initial_state = create_initial_state(
            request.user_query,
            investigation_id=investigation_id,
            business_type=request.business_type,
            location=request.location,
            target_customer=request.target_customer,
        )
        settings = get_settings()
        recursion_limit = max(50, int(settings.max_research_iterations) * 25)

        logger.info(
            "Starting investigation id=%s query=%r",
            initial_state["investigation_id"],
            request.user_query,
        )

        final_state: InvestigationState = await self._graph.ainvoke(
            initial_state,
            {"recursion_limit": recursion_limit},
        )
        result = InvestigationResult.model_validate(final_state)

        logger.info(
            "Completed investigation id=%s status=%s iteration=%s",
            result.investigation_id,
            result.status,
            result.iteration,
        )
        return result

    @staticmethod
    def _validate_request(
        payload: InvestigationRequest | dict[str, str],
    ) -> InvestigationRequest:
        if isinstance(payload, InvestigationRequest):
            return payload
        try:
            return InvestigationRequest.model_validate(payload)
        except ValidationError as exc:
            raise InvestigationInputError(
                "Invalid investigation input",
                details=str(exc),
            ) from exc
