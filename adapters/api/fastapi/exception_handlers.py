from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from entrypoints.api.error_presenter import present_api_error


CANON_API_FASTAPI_EXCEPTION_HANDLERS_FINAL_OWNER = True


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        payload = present_api_error(exc)
        return JSONResponse(
            status_code=500,
            content=payload.model_dump(),
        )
