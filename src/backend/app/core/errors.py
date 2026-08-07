"""Consistent error serialization and centralized exception handling.

A uniform error envelope is returned for every failure mode so that clients and
monitoring systems parse errors deterministically. Internal details are withheld
from responses to avoid leaking implementation specifics.

Handlers accept the base Exception type to satisfy the framework handler
signature and narrow to the concrete type only where specific attributes are
required; the dispatcher guarantees each handler receives its registered type.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import EntityNotFoundError, InvalidObjectIdError

logger = logging.getLogger(__name__)


def _envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    http_exc = cast(StarletteHTTPException, exc)
    return JSONResponse(
        status_code=http_exc.status_code,
        content=_envelope(code="http_error", message=str(http_exc.detail)),
    )


async def _validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    validation_exc = cast(RequestValidationError, exc)
    # Status 422 is referenced numerically to remain agnostic to the framework
    # constant that was renamed across Starlette versions.
    return JSONResponse(
        status_code=422,
        content=_envelope(
            code="validation_error",
            message="Request validation failed",
            details=validation_exc.errors(),
        ),
    )


async def _invalid_object_id_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=_envelope(code="invalid_identifier", message=str(exc) or "Invalid identifier"),
    )


async def _not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=_envelope(code="not_found", message=str(exc) or "Resource not found"),
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Full error context is logged server-side; the response withholds internals
    # to prevent information disclosure.
    logger.error("unhandled exception", exc_info=exc, extra={"path": request.url.path})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_envelope(code="internal_error", message="An internal error occurred"),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(InvalidObjectIdError, _invalid_object_id_handler)
    app.add_exception_handler(EntityNotFoundError, _not_found_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
