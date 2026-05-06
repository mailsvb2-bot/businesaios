from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


CANON_CLIENT_OUTCOME_COMMERCIAL_STATE_API_MODELS = True


class ClientOutcomeCommercialStateResponse(BaseModel):
    found: bool
    order_id: str = ''
    lead_id: str = ''
    created_at: str = ''
    updated_at: str = ''
    commercial_status: str = ''
    order: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    billable_record: dict[str, Any] | None = None
    revenue_before_reversal: dict[str, Any] | None = None
    dispute: dict[str, Any] | None = None
    reversal: dict[str, Any] | None = None
    revenue_after_reversal: dict[str, Any] | None = None
    admin_summary: dict[str, Any] | None = None
