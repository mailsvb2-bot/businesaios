from __future__ import annotations

from typing import Any

from pydantic import BaseModel


CANON_CLIENT_OUTCOME_CORRECTED_ECONOMICS_API_MODELS = True


class ClientOutcomeCorrectedEconomicsResponse(BaseModel):
    found: bool
    order_id: str = ''
    lead_id: str = ''
    created_at: str = ''
    updated_at: str = ''
    economics_status: str = ''
    corrected_revenue: dict[str, Any] | None = None
    reversal: dict[str, Any] | None = None
    refund_preview: dict[str, Any] | None = None
    refund_request: dict[str, Any] | None = None
