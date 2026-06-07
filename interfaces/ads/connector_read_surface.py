from __future__ import annotations

from datetime import date
from typing import Any, Optional, TypeVar
from collections.abc import Awaitable, Callable, Iterable, Sequence

T = TypeVar("T")


async def list_campaigns_with_token(
    *,
    tenant_id: str,
    account_id: str,
    get_access_token: Callable[..., Awaitable[str]],
    provider_list_campaigns: Callable[..., Awaitable[Sequence[dict[str, Any]]]],
    campaign_mapper: Callable[..., T],
) -> tuple[T, ...]:
    access_token = await get_access_token(tenant_id=tenant_id, account_id=account_id)
    rows = await provider_list_campaigns(
        tenant_id=tenant_id,
        account_id=account_id,
        access_token=access_token,
    )
    return tuple(campaign_mapper(account_id=account_id, row=dict(row)) for row in rows)


async def fetch_metrics_with_token(
    *,
    tenant_id: str,
    account_id: str,
    level: str,
    object_ids: Sequence[str] | None,
    date_from: date,
    date_to: date,
    get_access_token: Callable[..., Awaitable[str]],
    provider_fetch_metrics: Callable[..., Awaitable[Iterable[dict[str, Any]]]],
    metric_mapper: Callable[..., T],
) -> tuple[T, ...]:
    access_token = await get_access_token(tenant_id=tenant_id, account_id=account_id)
    rows = await provider_fetch_metrics(
        tenant_id=tenant_id,
        account_id=account_id,
        access_token=access_token,
        level=level,
        object_ids=object_ids,
        date_from=date_from,
        date_to=date_to,
    )
    return tuple(metric_mapper(account_id=account_id, level=level, row=dict(row)) for row in rows)


__all__ = ["fetch_metrics_with_token", "list_campaigns_with_token"]
