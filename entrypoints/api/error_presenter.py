from __future__ import annotations
CANON_API_ERROR_PRESENTER_FINAL_OWNER = True


from entrypoints.api.error_mapper import map_exception_to_error_code
from entrypoints.api.error_models import ErrorResponse


def present_api_error(exc: Exception) -> ErrorResponse:
    return ErrorResponse(
        error_code=map_exception_to_error_code(exc),
        message=str(exc) or exc.__class__.__name__,
        details={
            "exception_type": exc.__class__.__name__,
        },
    )
