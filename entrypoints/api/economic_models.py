from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


CANON_ECONOMIC_API_MODELS = True


class EconomicTruthResponse(BaseModel):
    found: bool
    scope_type: str = ''
    scope_id: str = ''
    tenant_id: str = ''
    business_id: str = ''
    truth: dict[str, Any] | None = None
    snapshot: dict[str, Any] | None = None
    widgets: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class EconomicExportResponse(BaseModel):
    found: bool
    scope_type: str = ''
    scope_id: str = ''
    algorithm: str = ''
    hash: str = ''
    verified: bool = False
    export_ready: bool = False
    payload: dict[str, Any] | None = None
