"""HTTP exception handlers for the public API."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.schemas import ErrorResponse
from app.core.exceptions import (
    InvestigationConflictError,
    InvestigationInputError,
    InvestigationNotFoundError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach JSON error handlers for 400 / 404 / 409 / 500 responses."""

    @app.exception_handler(InvestigationNotFoundError)
    async def not_found_handler(
        request: Request,
        exc: InvestigationNotFoundError,
    ) -> JSONResponse:
        del request
        body = ErrorResponse(code="not_found", message=exc.message)
        return JSONResponse(status_code=404, content=body.model_dump())

    @app.exception_handler(InvestigationInputError)
    async def input_error_handler(
        request: Request,
        exc: InvestigationInputError,
    ) -> JSONResponse:
        del request
        body = ErrorResponse(
            code="invalid_request",
            message=exc.message,
            details=exc.details,
        )
        return JSONResponse(status_code=400, content=body.model_dump())

    @app.exception_handler(InvestigationConflictError)
    async def conflict_handler(
        request: Request,
        exc: InvestigationConflictError,
    ) -> JSONResponse:
        del request
        body = ErrorResponse(code="conflict", message=exc.message)
        return JSONResponse(status_code=409, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request
        body = ErrorResponse(
            code="invalid_request",
            message="Invalid request",
            details=_summarize_validation(exc),
        )
        return JSONResponse(status_code=400, content=body.model_dump())

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        del request
        status = exc.status_code
        if status == 404:
            code = "not_found"
            message = str(exc.detail) if exc.detail else "Resource not found"
        elif status == 400:
            code = "invalid_request"
            message = str(exc.detail) if exc.detail else "Invalid request"
        else:
            code = "http_error"
            message = str(exc.detail) if exc.detail else "Request failed"
        body = ErrorResponse(code=code, message=message)
        return JSONResponse(status_code=status, content=body.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled application error path=%s", request.url.path)
        del exc
        body = ErrorResponse(
            code="internal_error",
            message="An unexpected application error occurred",
        )
        return JSONResponse(status_code=500, content=body.model_dump())


def _summarize_validation(exc: RequestValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors()[:8]:
        loc = ".".join(str(item) for item in error.get("loc", ()) if item != "body")
        msg = error.get("msg", "invalid")
        parts.append(f"{loc}: {msg}" if loc else str(msg))
    return "; ".join(parts) if parts else "Request validation failed"
