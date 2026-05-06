from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CANON_CLIENT_OUTCOME_CONTROL_PLANE_MODELS = True


@dataclass(frozen=True, slots=True)
class ClientOutcomeAdminSummary:
    tenant_id: str
    business_id: str
    order_id: str
    package_id: str
    requested_clients: int
    verified_clients: int
    billable_clients: int
    reversed_clients: int
    open_disputes: int
    reversed_disputes: int
    gross_revenue: float
    net_revenue: float
    currency: str


@dataclass(frozen=True, slots=True)
class ClientOutcomeAdminWidgetPayload:
    widget_id: str
    kind: str
    payload: dict[str, Any]
