from __future__ import annotations

"""Shared entity mappers for read-only ads connectors.

These helpers intentionally stay small and declarative. They reduce connector
copy-paste while keeping provider-specific field precedence explicit in the
connector call sites.
"""

from typing import Any, Dict, Sequence

from .base import AdsObjectRef, AdsPlatform, Campaign, MetricPoint
from .connector_mapping_support import (
    parse_metric_day,
    parse_optional_budget,
    resolve_first_nonempty,
    resolve_first_present,
)
from .connector_shared import as_float, as_int, as_optional_float, as_optional_int, safe_ratio


def build_campaign_from_row(
    *,
    platform: AdsPlatform,
    account_id: str,
    row: dict[str, Any],
    connector_name: str,
    id_keys: Sequence[str],
    budget_keys: Sequence[str],
    name_keys: Sequence[str],
    status_keys: Sequence[str],
    objective_keys: Sequence[str],
) -> Campaign:
    campaign_id = resolve_first_nonempty(*(row.get(key) for key in id_keys))
    if not campaign_id:
        from .base import AdsConnectorError

        raise AdsConnectorError(f"{connector_name}: campaign row missing id")
    daily_budget = parse_optional_budget(*(row.get(key) for key in budget_keys))
    objective = resolve_first_nonempty(*(row.get(key) for key in objective_keys), default="") or None
    return Campaign(
        ref=AdsObjectRef(
            platform=platform,
            account_id=account_id,
            object_type="campaign",
            object_id=campaign_id,
        ),
        name=resolve_first_nonempty(*(row.get(key) for key in name_keys), default=campaign_id),
        status=resolve_first_nonempty(*(row.get(key) for key in status_keys), default="unknown"),
        objective=objective,
        raw=dict(row),
        daily_budget=daily_budget,
    )


def build_metric_point_from_row(
    *,
    platform: AdsPlatform,
    account_id: str,
    level: str,
    row: dict[str, Any],
    connector_name: str,
    object_id_keys: Sequence[str],
    day_keys: Sequence[str],
    spend_keys: Sequence[str],
    spend_scale: float | None = None,
    conversion_keys: Sequence[str],
    revenue_keys: Sequence[str],
) -> MetricPoint:
    object_type = resolve_first_nonempty(level, row.get("object_type"), default="campaign")
    object_id = resolve_first_nonempty(*(row.get(key) for key in object_id_keys), default=account_id)
    day = parse_metric_day(row=row, candidate_keys=day_keys, connector_name=connector_name)
    impressions = as_int(row.get("impressions"))
    clicks = as_int(row.get("clicks"))

    spend_default = None
    if spend_scale is not None and spend_keys:
        spend_default = as_float(row.get(spend_keys[-1]), scale=float(spend_scale))
    spend = as_float(row.get(spend_keys[0]), default=spend_default) if spend_keys else 0.0

    conversions_raw = resolve_first_present(*(row.get(key) for key in conversion_keys))
    revenue_raw = resolve_first_present(*(row.get(key) for key in revenue_keys))
    conversions = as_optional_int(conversions_raw)
    revenue = as_optional_float(revenue_raw)
    return MetricPoint(
        ref=AdsObjectRef(
            platform=platform,
            account_id=account_id,
            object_type=object_type,
            object_id=object_id,
        ),
        day=day,
        impressions=impressions,
        clicks=clicks,
        spend=spend,
        conversions=conversions,
        revenue=revenue,
        cpa=safe_ratio(spend, conversions),
        cpc=safe_ratio(spend, clicks),
        ctr=safe_ratio(clicks, impressions),
        currency=(str(row.get("currency") or "").strip() or None),
        raw=dict(row),
    )


__all__ = ["build_campaign_from_row", "build_metric_point_from_row"]
