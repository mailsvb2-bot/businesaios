from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class OAuthConnectRequest:
    tenant_id: str
    user_id: str
    redirect_uri: str
    state: str
@dataclass(frozen=True)
class OAuthConnectResult:
    authorization_url: str
    raw: dict[str, Any] | None = None
@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    name: str
    status: str
    daily_budget: float | None = None
    objective: str | None = None
    raw: dict[str, Any] | None = None
@dataclass(frozen=True)
class MetricsPoint:
    day: date
    object_type: str
    object_id: str
    impressions: int
    clicks: int
    spend: float
    cpa: float | None = None
    conversions: int | None = None
    revenue: float | None = None
    extra: dict[str, Any] | None = None
@dataclass(frozen=True)
class CreateOrUpdateRequest:
    object_type: str
    payload: dict[str, Any]
    idempotency_key: str | None = None
@dataclass(frozen=True)
class CreateOrUpdateResponse:
    ok: bool
    platform_object_id: str | None = None
    raw: dict[str, Any] | None = None
