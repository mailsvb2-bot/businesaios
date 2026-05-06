from __future__ import annotations

"""Ads Connector Layer (canonical contract).

Stage model:
  1) Read-only: connect + list inventory + fetch metrics
  2) Recommendations: write surface exists but must be invoked only after human approval
  3) Autopilot: write surface invoked by AI only behind guardrails + audit

This package provides *interfaces + skeletons*. Real production integrations must
remain behind explicit entitlement checks and budget guardrails.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Dict, Iterable, Optional, Protocol, Sequence

from .errors import AdsConnectorError


class AdsPlatform(str, Enum):
    META = "meta"
    YANDEX_DIRECT = "yandex_direct"
    VK = "vk"
    TELEGRAM_ADS = "telegram_ads"
    GOOGLE_ADS = "google_ads"
    TIKTOK_ADS = "tiktok_ads"
    OTHER = "other"


@dataclass(frozen=True)
class ConnectedAccount:
    platform: AdsPlatform
    account_id: str
    display_name: str
    scopes: Sequence[str]
    created_at_iso: str


@dataclass(frozen=True)
class OAuthAuthorizeURL:
    url: str
    state: str


@dataclass(frozen=True)
class AdsObjectRef:
    platform: AdsPlatform
    account_id: str
    object_type: str  # "campaign" | "adset" | "ad"
    object_id: str


@dataclass(frozen=True)
class Campaign:
    ref: AdsObjectRef
    name: str
    status: str
    objective: Optional[str]
    raw: Dict[str, Any]

    # Optional normalized fields (connector-specific availability).
    # Keeping them optional preserves backward compatibility while allowing
    # richer UX without reading connector-specific raw payloads.
    daily_budget: Optional[float] = None

    @property
    def campaign_id(self) -> str:
        """Interop convenience: campaign id (same as ref.object_id)."""

        return self.ref.object_id


@dataclass(frozen=True)
class MetricPoint:
    ref: AdsObjectRef
    day: date
    impressions: int
    clicks: int
    spend: float
    conversions: Optional[int] = None
    revenue: Optional[float] = None
    cpa: Optional[float] = None
    cpc: Optional[float] = None
    ctr: Optional[float] = None
    currency: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None



class AdsReadConnector(Protocol):
    """Read-only subset of the connector contract.

    Important: this surface must never include write methods.
    """

    platform: AdsPlatform

    async def connect(self, *, tenant_id: str, redirect_uri: str) -> OAuthAuthorizeURL: ...
    async def exchange_code(self, *, tenant_id: str, code: str, redirect_uri: str) -> ConnectedAccount: ...
    async def disconnect(self, *, tenant_id: str, account_id: str) -> None: ...

    async def list_campaigns(self, *, tenant_id: str, account_id: str) -> Sequence[Campaign]: ...

    async def fetch_metrics(
        self,
        *,
        tenant_id: str,
        account_id: str,
        level: str,
        object_ids: Optional[Sequence[str]],
        date_from: date,
        date_to: date,
    ) -> Iterable[MetricPoint]: ...


class AdsWriteConnector(AdsReadConnector, Protocol):
    """Write-capable connector contract (must be gated by guardrails + audit).

    Only AdsWriteGateway should depend on this protocol.
    """

    async def create_or_update(
        self,
        *,
        tenant_id: str,
        account_id: str,
        object_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]: ...


class AdsConnector(AdsWriteConnector, Protocol):
    """Backward-compatible alias: full connector contract.

    Use AdsReadConnector / AdsWriteConnector for strict surfaces.
    """

    platform: AdsPlatform

