"""Operational errors that map cleanly to HTTP responses, plus the global exception handlers."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("bookleaf")


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def bad_request(msg, details=None): return AppError(400, "BAD_REQUEST", msg, details)
def unauthorized(msg="Authentication required"): return AppError(401, "UNAUTHORIZED", msg)
def forbidden(msg="You do not have access to this resource"): return AppError(403, "FORBIDDEN", msg)
def not_found(msg="Resource not found"): return AppError(404, "NOT_FOUND", msg)


def _body(code, message, details=None):
    err = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return {"error": err}


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, e: AppError):
        return JSONResponse(_body(e.code, e.message, e.details), status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        details = []
        for err in e.errors():
            loc = [str(p) for p in err["loc"] if p not in ("body", "query", "path")]
            msg = err["msg"].removeprefix("Value error, ")
            details.append({"field": ".".join(loc), "message": msg})
        return JSONResponse(_body("VALIDATION_ERROR", "Request validation failed", details), status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, e: StarletteHTTPException):
        if e.status_code == 404:
            return JSONResponse(_body("NOT_FOUND", f"No route for {request.method} {request.url.path}"), status_code=404)
        return JSONResponse(_body("HTTP_ERROR", str(e.detail)), status_code=e.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, e: Exception):
        log.exception("unhandled error", exc_info=e)
        return JSONResponse(_body("INTERNAL_ERROR", "Something went wrong on our side. Please try again."), status_code=500)
