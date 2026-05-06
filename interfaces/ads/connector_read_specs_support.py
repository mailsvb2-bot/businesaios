from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, Optional, Sequence

from .base import AdsPlatform, Campaign, MetricPoint
from .connector_entity_support import build_campaign_from_row, build_metric_point_from_row
from .connector_read_ops_support import provider_fetch_metric_rows, provider_list_campaign_rows


@dataclass(frozen=True)
class CampaignReadSpec:
    connector_name: str
    provider_method_name: str
    id_keys: Sequence[str]
    budget_keys: Sequence[str]
    name_keys: Sequence[str]
    status_keys: Sequence[str]
    objective_keys: Sequence[str]


@dataclass(frozen=True)
class MetricReadSpec:
    connector_name: str
    provider_method_name: str
    object_id_keys: Sequence[str]
    day_keys: Sequence[str]
    spend_keys: Sequence[str]
    conversion_keys: Sequence[str]
    revenue_keys: Sequence[str]
    spend_scale: float | None = None


async def provider_campaign_rows_from_spec(
    *,
    http: Any,
    platform: AdsPlatform,
    tenant_id: str,
    account_id: str,
    access_token: str,
    spec: CampaignReadSpec,
) -> Sequence[dict[str, Any]]:
    return await provider_list_campaign_rows(
        http=http,
        connector_name=spec.connector_name,
        provider_method_name=spec.provider_method_name,
        platform_value=str(platform.value),
        tenant_id=tenant_id,
        account_id=account_id,
        access_token=access_token,
    )


async def provider_metric_rows_from_spec(
    *,
    http: Any,
    platform: AdsPlatform,
    tenant_id: str,
    account_id: str,
    access_token: str,
    level: str,
    object_ids: Optional[Sequence[str]],
    date_from: date,
    date_to: date,
    spec: MetricReadSpec,
) -> Iterable[dict[str, Any]]:
    return await provider_fetch_metric_rows(
        http=http,
        connector_name=spec.connector_name,
        provider_method_name=spec.provider_method_name,
        platform_value=str(platform.value),
        tenant_id=tenant_id,
        account_id=account_id,
        access_token=access_token,
        level=level,
        object_ids=object_ids,
        date_from=date_from,
        date_to=date_to,
    )


def campaign_from_row_with_spec(
    *,
    platform: AdsPlatform,
    account_id: str,
    row: Dict[str, Any],
    spec: CampaignReadSpec,
) -> Campaign:
    return build_campaign_from_row(
        platform=platform,
        account_id=account_id,
        row=row,
        connector_name=spec.connector_name,
        id_keys=spec.id_keys,
        budget_keys=spec.budget_keys,
        name_keys=spec.name_keys,
        status_keys=spec.status_keys,
        objective_keys=spec.objective_keys,
    )



def metric_from_row_with_spec(
    *,
    platform: AdsPlatform,
    account_id: str,
    level: str,
    row: Dict[str, Any],
    spec: MetricReadSpec,
) -> MetricPoint:
    return build_metric_point_from_row(
        platform=platform,
        account_id=account_id,
        level=level,
        row=row,
        connector_name=spec.connector_name,
        object_id_keys=spec.object_id_keys,
        day_keys=spec.day_keys,
        spend_keys=spec.spend_keys,
        spend_scale=spec.spend_scale,
        conversion_keys=spec.conversion_keys,
        revenue_keys=spec.revenue_keys,
    )


__all__ = [
    "CampaignReadSpec",
    "MetricReadSpec",
    "campaign_from_row_with_spec",
    "metric_from_row_with_spec",
    "provider_campaign_rows_from_spec",
    "provider_metric_rows_from_spec",
]
