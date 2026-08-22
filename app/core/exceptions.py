from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError


class AppException(Exception):
    def __init__(
        self, message: str, status_code: int = 400, details: dict | None = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"message": exc.message, "details": exc.details}},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError | ValidationError
) -> JSONResponse:
    errors = exc.errors() if hasattr(exc, "errors") else []
    sanitized_errors = []
    for error in errors:
        error_copy = dict(error)
        if "ctx" in error_copy and "error" in error_copy["ctx"]:
            ctx_copy = dict(error_copy["ctx"])
            ctx_copy["error"] = str(ctx_copy["error"])
            error_copy["ctx"] = ctx_copy
        sanitized_errors.append(error_copy)
        
    return JSONResponse(
        status_code=422,
        content={"error": {"message": "Validation Error", "details": sanitized_errors}},
    )
