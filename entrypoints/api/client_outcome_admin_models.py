from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


CANON_CLIENT_OUTCOME_ADMIN_API_MODELS = True


class ClientOutcomeOrderInput(BaseModel):
    order_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    package_label: str = Field(min_length=1)
    requested_clients: int = Field(ge=1)
    price_per_verified_client: float = Field(ge=0.0)
    currency: str = Field(min_length=1)
    trust_tier: str = Field(min_length=1)
    created_at: str = Field(min_length=1)


class ClientOutcomeEconomicSnapshotInput(BaseModel):
    verified_clients: int = Field(ge=0)
    billable_clients: int = Field(ge=0)
    billed_revenue: float
    acquisition_cost: float
    gross_margin: float
    cac: float
    revenue_per_client: float
    margin_per_client: float
    currency: str = Field(min_length=1)


class ClientOutcomeAdminSummaryRequest(BaseModel):
    order: ClientOutcomeOrderInput
    economic_snapshot: ClientOutcomeEconomicSnapshotInput


class ClientOutcomeAdminSummaryResponse(BaseModel):
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
    widgets: tuple[dict[str, Any], ...]
