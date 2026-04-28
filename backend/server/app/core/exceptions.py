"""
FarmShield Backend — Exception Handlers.

All error responses return a consistent JSON shape:
  {"detail": "...", "type": "VALIDATION_ERROR | AUTH_ERROR | NOT_FOUND | INTERNAL_ERROR"}

No raw Python tracebacks or SQLAlchemy errors ever reach the API response.
"""

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger(__name__)


def _error_type_from_status(status_code: int) -> str:
    """Derive a type string from an HTTP status code."""
    if status_code == 401:
        return "AUTH_ERROR"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 422:
        return "VALIDATION_ERROR"
    if status_code >= 500:
        return "INTERNAL_ERROR"
    return "CLIENT_ERROR"


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app instance."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "validation_error",
            path=str(request.url),
            errors=exc.errors(),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": str(exc.errors()),
                "type": "VALIDATION_ERROR",
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        logger.warning(
            "http_exception",
            path=str(request.url),
            status_code=exc.status_code,
            detail=exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": str(exc.detail),
                "type": _error_type_from_status(exc.status_code),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            path=str(request.url),
            exc_type=type(exc).__name__,
            exc_message=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal error occurred. Please try again later.",
                "type": "INTERNAL_ERROR",
            },
        )
