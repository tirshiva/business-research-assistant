"""Investigation HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request

from app.api.schemas import (
    AdditionalResearchRequest,
    CreateInvestigationRequest,
    ErrorResponse,
    EvidenceListResponse,
    InvestigationCreatedResponse,
    InvestigationReportResponse,
    InvestigationResponse,
    InvestigationStatusResponse,
)
from app.services.investigation_app import InvestigationAppService

router = APIRouter(prefix="/investigations", tags=["investigations"])

_ERROR_RESPONSES = {
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


def _service(request: Request) -> InvestigationAppService:
    return request.app.state.investigation_app_service


@router.post(
    "",
    response_model=InvestigationCreatedResponse,
    status_code=202,
    responses=_ERROR_RESPONSES,
)
async def create_investigation(
    payload: CreateInvestigationRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> InvestigationCreatedResponse:
    """Create an investigation and start research in the background."""
    service = _service(request)
    investigation_id, status = await service.create(payload.query)
    background_tasks.add_task(service.run_background, investigation_id)
    return InvestigationCreatedResponse(id=investigation_id, status=status)


@router.get(
    "/{investigation_id}",
    response_model=InvestigationResponse,
    responses=_ERROR_RESPONSES,
)
async def get_investigation(
    investigation_id: str,
    request: Request,
) -> InvestigationResponse:
    return await _service(request).get_investigation(investigation_id)


@router.get(
    "/{investigation_id}/status",
    response_model=InvestigationStatusResponse,
    responses=_ERROR_RESPONSES,
)
async def get_investigation_status(
    investigation_id: str,
    request: Request,
) -> InvestigationStatusResponse:
    return await _service(request).get_status(investigation_id)


@router.get(
    "/{investigation_id}/evidence",
    response_model=EvidenceListResponse,
    responses=_ERROR_RESPONSES,
)
async def get_investigation_evidence(
    investigation_id: str,
    request: Request,
) -> EvidenceListResponse:
    return await _service(request).get_evidence(investigation_id)


@router.get(
    "/{investigation_id}/report",
    response_model=InvestigationReportResponse,
    responses=_ERROR_RESPONSES,
)
async def get_investigation_report(
    investigation_id: str,
    request: Request,
) -> InvestigationReportResponse:
    return await _service(request).get_report(investigation_id)


@router.post(
    "/{investigation_id}/research",
    response_model=InvestigationCreatedResponse,
    status_code=202,
    responses=_ERROR_RESPONSES,
)
async def trigger_additional_research(
    investigation_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    payload: AdditionalResearchRequest | None = None,
) -> InvestigationCreatedResponse:
    """Run another research pass for an existing investigation."""
    service = _service(request)
    tasks = list(payload.tasks) if payload else []
    _, status = await service.request_additional_research(
        investigation_id,
        tasks=tasks,
    )
    background_tasks.add_task(service.run_background, investigation_id)
    return InvestigationCreatedResponse(id=investigation_id, status=status)
