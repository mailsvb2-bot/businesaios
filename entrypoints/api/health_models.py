from __future__ import annotations

from pydantic import BaseModel, Field


class HealthCheckView(BaseModel):
    name: str
    status: str
    signal: str
    summary: str
    details: dict[str, object] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    startup_audit_events: list[str] = Field(default_factory=list)
    checks: list[HealthCheckView] = Field(default_factory=list)
    details: dict[str, object] = Field(default_factory=dict)
