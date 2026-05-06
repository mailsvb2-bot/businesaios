from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


CANON_CLIENT_OUTCOME_ADMIN_VIEW_MODELS = True


class ClientOutcomeAdminViewResponse(BaseModel):
    found: bool
    order: dict[str, Any] | None = None
    lifecycle: dict[str, Any] | None = None
    commercial_state: dict[str, Any] | None = None
    corrected_economics: dict[str, Any] | None = None
    reconciliation: dict[str, Any] | None = None
    widgets: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
