from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

CANON_CLIENT_OUTCOME_API_MODELS = True


class ClientOutcomePackageResponse(BaseModel):
    package_id: str
    label: str
    requested_clients: int
    price_per_verified_client: float
    currency: str
    attribution_window_days: int
    trust_tier: str


class SelectClientOutcomePackageRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    package_id: str = ''
    requested_clients: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    execute_now: bool = False


class ClientOutcomeOrderResponse(BaseModel):
    order_id: str
    tenant_id: str
    business_id: str
    package_id: str
    package_label: str
    requested_clients: int
    price_per_verified_client: float
    currency: str
    trust_tier: str
    created_at: str


class ClientOutcomeExecuteResponse(BaseModel):
    order: ClientOutcomeOrderResponse
    execution: dict[str, Any]


class ClientOutcomeOrderLookupResponse(BaseModel):
    found: bool
    order: ClientOutcomeOrderResponse | None = None


class AmendClientOutcomeOrderRequest(BaseModel):
    package_id: str = ''
    requested_clients: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClientOutcomeOrderAmendResponse(BaseModel):
    order: ClientOutcomeOrderResponse
    amendment_count: int = 0
    amendments: tuple[dict[str, Any], ...] = ()
