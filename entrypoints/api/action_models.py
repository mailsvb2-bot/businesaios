from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExecuteActionRequest(BaseModel):
    action_type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class ExecuteActionResponse(BaseModel):
    status: str
    action_type: str
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    capability_view: dict[str, Any] = Field(default_factory=dict)
