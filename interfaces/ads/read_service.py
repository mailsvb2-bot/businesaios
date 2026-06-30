"""Ads read-only service surface.

Design goal:
  - do NOT expose connector objects outside of runtime wiring
  - provide a narrow, stable API for read-only operations

This prevents "second paths" where some caller could accidentally reach
write methods (even if currently proxied). The only write surface must be the
dedicated gateway with guardrails + audit.
"""

from __future__ import annotations

from datetime import date
from collections.abc import Iterable, Sequence
from interfaces.ads.base import (
    AdsPlatform,
    AdsReadConnector,
    Campaign,
    ConnectedAccount,
    MetricPoint,
    OAuthAuthorizeURL,
)
from interfaces.ads.registry import AdsConnectorRegistry

class AdsReadService:
    """Read-only facade over registered ads connectors."""

    def __init__(self, *, registry: AdsConnectorRegistry[AdsReadConnector]) -> None:
        self._registry = registry

    async def connect(self, *, tenant_id: str, platform: AdsPlatform, redirect_uri: str) -> OAuthAuthorizeURL:
        c = self._registry.get(platform)
        return await c.connect(tenant_id=tenant_id, redirect_uri=redirect_uri)

    async def exchange_code(
        self,
        *,
        tenant_id: str,
        platform: AdsPlatform,
        code: str,
        redirect_uri: str,
    ) -> ConnectedAccount:
        c = self._registry.get(platform)
        return await c.exchange_code(tenant_id=tenant_id, code=code, redirect_uri=redirect_uri)

    async def disconnect(self, *, tenant_id: str, platform: AdsPlatform, account_id: str) -> None:
        c = self._registry.get(platform)
        return await c.disconnect(tenant_id=tenant_id, account_id=account_id)

    async def list_campaigns(self, *, tenant_id: str, platform: AdsPlatform, account_id: str) -> Sequence[Campaign]:
        c = self._registry.get(platform)
        return await c.list_campaigns(tenant_id=tenant_id, account_id=account_id)

    async def fetch_metrics(
        self,
        *,
        tenant_id: str,
        platform: AdsPlatform,
        account_id: str,
        level: str,
        object_ids: Sequence[str] | None,
        date_from: date,
        date_to: date,
    ) -> Iterable[MetricPoint]:
        c = self._registry.get(platform)
        return await c.fetch_metrics(
            tenant_id=tenant_id,
            account_id=account_id,
            level=level,
            object_ids=object_ids,
            date_from=date_from,
            date_to=date_to,
        )
