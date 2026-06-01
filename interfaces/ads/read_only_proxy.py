from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, Optional, Sequence

from .base import (
    AdsPlatform,
    AdsReadConnector,
    AdsWriteConnector,
    Campaign,
    ConnectedAccount,
    MetricPoint,
    OAuthAuthorizeURL,
)


@dataclass
class ReadOnlyAdsConnector(AdsReadConnector):
    """Proxy that guarantees a connector instance cannot mutate ad platforms.

    Use this when exposing connector objects to the rest of the system.
    All write operations must go through AdsWriteGateway.
    """

    inner: AdsWriteConnector

    @property
    def platform(self) -> AdsPlatform:
        return self.inner.platform

    async def connect(self, *, tenant_id: str, redirect_uri: str) -> OAuthAuthorizeURL:
        return await self.inner.connect(tenant_id=tenant_id, redirect_uri=redirect_uri)

    async def exchange_code(self, *, tenant_id: str, code: str, redirect_uri: str) -> ConnectedAccount:
        return await self.inner.exchange_code(tenant_id=tenant_id, code=code, redirect_uri=redirect_uri)

    async def disconnect(self, *, tenant_id: str, account_id: str) -> None:
        return await self.inner.disconnect(tenant_id=tenant_id, account_id=account_id)

    async def list_campaigns(self, *, tenant_id: str, account_id: str) -> Sequence[Campaign]:
        return await self.inner.list_campaigns(tenant_id=tenant_id, account_id=account_id)

    async def fetch_metrics(
        self,
        *,
        tenant_id: str,
        account_id: str,
        level: str,
        object_ids: Sequence[str] | None,
        date_from: date,
        date_to: date,
    ) -> Iterable[MetricPoint]:
        return await self.inner.fetch_metrics(
            tenant_id=tenant_id,
            account_id=account_id,
            level=level,
            object_ids=object_ids,
            date_from=date_from,
            date_to=date_to,
        )

    async def create_or_update(self, *, tenant_id: str, account_id: str, object_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise PermissionError('Direct ads writes are forbidden. Use AdsWriteGateway (guardrails + audit).')
