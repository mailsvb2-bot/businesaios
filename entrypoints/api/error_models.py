from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error_code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict = Field(default_factory=dict)
