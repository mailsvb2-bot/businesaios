from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, Optional, Sequence

from .base import Campaign, MetricPoint
from .connector_read_ops_support import fetch_metrics_via_token, list_campaigns_via_token
from .connector_read_specs_support import (
    CampaignReadSpec,
    MetricReadSpec,
    campaign_from_row_with_spec,
    metric_from_row_with_spec,
    provider_campaign_rows_from_spec,
    provider_metric_rows_from_spec,
)


async def provider_list_campaigns_from_spec_adapter(
    *,
    http: Any,
    platform: Any,
    tenant_id: str,
    account_id: str,
    access_token: str,
    spec: CampaignReadSpec,
) -> Sequence[dict[str, Any]]:
    return await provider_campaign_rows_from_spec(
        http=http,
        platform=platform,
        tenant_id=tenant_id,
        account_id=account_id,
        access_token=access_token,
        spec=spec,
    )


async def provider_fetch_metrics_from_spec_adapter(
    *,
    http: Any,
    platform: Any,
    tenant_id: str,
    account_id: str,
    access_token: str,
    level: str,
    object_ids: Sequence[str] | None,
    date_from: date,
    date_to: date,
    spec: MetricReadSpec,
) -> Iterable[dict[str, Any]]:
    return await provider_metric_rows_from_spec(
        http=http,
        platform=platform,
        tenant_id=tenant_id,
        account_id=account_id,
        access_token=access_token,
        level=level,
        object_ids=object_ids,
        date_from=date_from,
        date_to=date_to,
        spec=spec,
    )


def campaign_from_spec_adapter(*, platform: Any, account_id: str, row: dict[str, Any], spec: CampaignReadSpec) -> Campaign:
    return campaign_from_row_with_spec(platform=platform, account_id=account_id, row=row, spec=spec)


def metric_from_spec_adapter(
    *,
    platform: Any,
    account_id: str,
    level: str,
    row: dict[str, Any],
    spec: MetricReadSpec,
) -> MetricPoint:
    return metric_from_row_with_spec(platform=platform, account_id=account_id, level=level, row=row, spec=spec)


async def list_campaigns_from_spec_adapter(
    *,
    tenant_id: str,
    account_id: str,
    get_access_token: Any,
    provider_list_campaigns: Any,
    platform: Any,
    spec: CampaignReadSpec,
) -> Sequence[Campaign]:
    return await list_campaigns_via_token(
        tenant_id=tenant_id,
        account_id=account_id,
        get_access_token=get_access_token,
        provider_list_campaigns=provider_list_campaigns,
        campaign_mapper=lambda *, account_id, row: campaign_from_spec_adapter(
            platform=platform,
            account_id=account_id,
            row=row,
            spec=spec,
        ),
    )


async def fetch_metrics_from_spec_adapter(
    *,
    tenant_id: str,
    account_id: str,
    level: str,
    object_ids: Sequence[str] | None,
    date_from: date,
    date_to: date,
    get_access_token: Any,
    provider_fetch_metrics: Any,
    platform: Any,
    spec: MetricReadSpec,
) -> Iterable[MetricPoint]:
    return await fetch_metrics_via_token(
        tenant_id=tenant_id,
        account_id=account_id,
        level=level,
        object_ids=object_ids,
        date_from=date_from,
        date_to=date_to,
        get_access_token=get_access_token,
        provider_fetch_metrics=provider_fetch_metrics,
        metric_mapper=lambda *, account_id, level, row: metric_from_spec_adapter(
            platform=platform,
            account_id=account_id,
            level=level,
            row=row,
            spec=spec,
        ),
    )


__all__ = [
    "campaign_from_spec_adapter",
    "fetch_metrics_from_spec_adapter",
    "list_campaigns_from_spec_adapter",
    "metric_from_spec_adapter",
    "provider_fetch_metrics_from_spec_adapter",
    "provider_list_campaigns_from_spec_adapter",
]
