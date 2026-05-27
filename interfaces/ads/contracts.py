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
    raw: Optional[Dict[str, Any]] = None
@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    name: str
    status: str
    daily_budget: Optional[float] = None
    objective: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None
@dataclass(frozen=True)
class MetricsPoint:
    day: date
    object_type: str
    object_id: str
    impressions: int
    clicks: int
    spend: float
    cpa: Optional[float] = None
    conversions: Optional[int] = None
    revenue: Optional[float] = None
    extra: Optional[Dict[str, Any]] = None
@dataclass(frozen=True)
class CreateOrUpdateRequest:
    object_type: str
    payload: Dict[str, Any]
    idempotency_key: Optional[str] = None
@dataclass(frozen=True)
class CreateOrUpdateResponse:
    ok: bool
    platform_object_id: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None
