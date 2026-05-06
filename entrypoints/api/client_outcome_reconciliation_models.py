from __future__ import annotations

from typing import Any

from pydantic import BaseModel


CANON_CLIENT_OUTCOME_RECONCILIATION_API_MODELS = True


class ClientOutcomeReconciliationResponse(BaseModel):
    found: bool
    order_id: str = ''
    lead_id: str = ''
    consistent: bool = False
    issues: tuple[str, ...] = ()
    commercial_status: str = ''
    economics_status: str = ''
    reversal_amount: float | None = None
    corrected_revenue: dict[str, Any] | None = None
    commercial_state: dict[str, Any] | None = None
    corrected_economics: dict[str, Any] | None = None
    lifecycle: dict[str, Any] | None = None
