from __future__ import annotations

from datetime import date
from typing import Any, Optional
from collections.abc import Iterable, Sequence

from .read_adapter import read_rows


async def provider_list_rows(
    *,
    http: Any,
    connector_name: str,
    provider_method_name: str,
    generic_platform: str,
    tenant_id: str,
    account_id: str,
    access_token: str,
) -> Sequence[dict[str, Any]]:
    return await read_rows(
        http=http,
        connector_name=connector_name,
        provider_method_name=provider_method_name,
        generic_method_name="list_campaigns",
        generic_platform=generic_platform,
        generic_method_label="campaigns",
        kwargs={
            "tenant_id": tenant_id,
            "account_id": account_id,
            "access_token": access_token,
        },
    )


async def provider_metric_rows(
    *,
    http: Any,
    connector_name: str,
    provider_method_name: str,
    generic_platform: str,
    tenant_id: str,
    account_id: str,
    access_token: str,
    level: str,
    object_ids: Sequence[str] | None,
    date_from: date,
    date_to: date,
) -> Iterable[dict[str, Any]]:
    return await read_rows(
        http=http,
        connector_name=connector_name,
        provider_method_name=provider_method_name,
        generic_method_name="fetch_metrics",
        generic_platform=generic_platform,
        generic_method_label="metrics",
        kwargs={
            "tenant_id": tenant_id,
            "account_id": account_id,
            "access_token": access_token,
            "level": level,
            "object_ids": object_ids,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


__all__ = ["provider_list_rows", "provider_metric_rows"]
