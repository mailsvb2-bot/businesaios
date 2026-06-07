from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, TypeVar
from collections.abc import Awaitable, Callable, Iterable, Sequence

from .base import Campaign, MetricPoint
from .connector_provider_support import provider_list_rows, provider_metric_rows
from .connector_read_surface import fetch_metrics_with_token, list_campaigns_with_token

CampaignMapper = Callable[..., Campaign]
MetricMapper = Callable[..., MetricPoint]
GetAccessToken = Callable[..., Awaitable[str]]


async def provider_list_campaign_rows(
    *,
    http: Any,
    connector_name: str,
    provider_method_name: str,
    platform_value: str,
    tenant_id: str,
    account_id: str,
    access_token: str,
) -> Sequence[dict[str, Any]]:
    return await provider_list_rows(
        http=http,
        connector_name=connector_name,
        provider_method_name=provider_method_name,
        generic_platform=platform_value,
        tenant_id=tenant_id,
        account_id=account_id,
        access_token=access_token,
    )


async def provider_fetch_metric_rows(
    *,
    http: Any,
    connector_name: str,
    provider_method_name: str,
    platform_value: str,
    tenant_id: str,
    account_id: str,
    access_token: str,
    level: str,
    object_ids: Sequence[str] | None,
    date_from: date,
    date_to: date,
) -> Iterable[dict[str, Any]]:
    return await provider_metric_rows(
        http=http,
        connector_name=connector_name,
        provider_method_name=provider_method_name,
        generic_platform=platform_value,
        tenant_id=tenant_id,
        account_id=account_id,
        access_token=access_token,
        level=level,
        object_ids=object_ids,
        date_from=date_from,
        date_to=date_to,
    )


async def list_campaigns_via_token(
    *,
    tenant_id: str,
    account_id: str,
    get_access_token: Callable[..., Awaitable[str]],
    provider_list_campaigns: Callable[..., Awaitable[Sequence[dict[str, Any]]]],
    campaign_mapper: Callable[..., Campaign],
) -> Sequence[Campaign]:
    return await list_campaigns_with_token(
        tenant_id=tenant_id,
        account_id=account_id,
        get_access_token=get_access_token,
        provider_list_campaigns=provider_list_campaigns,
        campaign_mapper=campaign_mapper,
    )


async def fetch_metrics_via_token(
    *,
    tenant_id: str,
    account_id: str,
    level: str,
    object_ids: Sequence[str] | None,
    date_from: date,
    date_to: date,
    get_access_token: Callable[..., Awaitable[str]],
    provider_fetch_metrics: Callable[..., Awaitable[Iterable[dict[str, Any]]]],
    metric_mapper: Callable[..., MetricPoint],
) -> Iterable[MetricPoint]:
    return await fetch_metrics_with_token(
        tenant_id=tenant_id,
        account_id=account_id,
        level=level,
        object_ids=object_ids,
        date_from=date_from,
        date_to=date_to,
        get_access_token=get_access_token,
        provider_fetch_metrics=provider_fetch_metrics,
        metric_mapper=metric_mapper,
    )


__all__ = [
    "fetch_metrics_via_token",
    "list_campaigns_via_token",
    "provider_fetch_metric_rows",
    "provider_list_campaign_rows",
]
