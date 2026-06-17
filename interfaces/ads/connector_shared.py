from __future__ import annotations

import hashlib
import json
from typing import Any
from collections.abc import Iterable, Mapping

from .base import AdsConnectorError, AdsPlatform
from .connector_value_coercion import as_float, as_int, as_optional_float, as_optional_int, safe_ratio


def _normalize_secret_value(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalized_mapping(payload: Any) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)
    raise AdsConnectorError("connector transport must return a mapping payload")


def _stable_jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _stable_jsonable(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_stable_jsonable(v) for v in value]
    if isinstance(value, set):
        return sorted(_stable_jsonable(v) for v in value)
    return value


def vault_get_secret(vault: Any | None, *, tenant_id: str | None, key: str) -> str | None:
    if vault is None:
        return None
    getter = getattr(vault, "get_secret", None)
    if not callable(getter):
        return None
    if tenant_id:
        try:
            value = _normalize_secret_value(getter(str(tenant_id), key))
            if value is not None:
                return value
        except TypeError:
            pass
    return _normalize_secret_value(getter(key))


async def http_post_compat(
    http: Any,
    *,
    platform: AdsPlatform,
    url: str,
    headers: dict[str, str],
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    post = getattr(http, "post", None)
    if callable(post):
        return _normalized_mapping(await post(url, headers=headers, data=data))
    request_fn = getattr(http, "request", None)
    if not callable(request_fn):
        raise AdsConnectorError("connector http client must implement post() or request()")
    return _normalized_mapping(await request_fn(
        "POST",
        url,
        headers=headers,
        data=data,
        platform=str(platform.value),
    ))


async def http_get_compat(
    http: Any,
    *,
    platform: AdsPlatform,
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    get = getattr(http, "get", None)
    if callable(get):
        return _normalized_mapping(await get(url, headers=headers, params=params))
    request_fn = getattr(http, "request", None)
    if not callable(request_fn):
        raise AdsConnectorError("connector http client must implement get() or request()")
    return _normalized_mapping(await request_fn(
        "GET",
        url,
        headers=headers,
        params=params,
        platform=str(platform.value),
    ))


def resolve_url_with_default(
    *,
    cfg_value: str | None,
    vault: Any | None,
    vault_key: str,
    default: str,
    tenant_id: str | None = None,
) -> str:
    normalized_cfg = _normalize_secret_value(cfg_value)
    if normalized_cfg is not None:
        return normalized_cfg
    value = vault_get_secret(vault, tenant_id=tenant_id, key=vault_key)
    if value:
        return str(value)
    return default


def resolve_url_required(
    *,
    cfg_value: str | None,
    vault: Any | None,
    vault_key: str,
    error_message: str,
    tenant_id: str | None = None,
) -> str:
    normalized_cfg = _normalize_secret_value(cfg_value)
    if normalized_cfg is not None:
        return normalized_cfg
    value = vault_get_secret(vault, tenant_id=tenant_id, key=vault_key)
    if value is None:
        raise AdsConnectorError(error_message)
    return str(value)


def resolve_secret_required(
    *,
    cfg_value: str | None,
    vault: Any | None,
    vault_key: str,
    error_message: str,
    tenant_id: str | None = None,
) -> str:
    normalized_cfg = _normalize_secret_value(cfg_value)
    if normalized_cfg is not None:
        return normalized_cfg
    value = vault_get_secret(vault, tenant_id=tenant_id, key=vault_key)
    if value is None:
        raise AdsConnectorError(error_message)
    return value


def stable_payload_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(_stable_jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_rows(payload: Any, *, key: str) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping):
        rows = payload.get(key, [])
    else:
        rows = payload
    if isinstance(rows, Mapping):
        rows = [rows]
    if not isinstance(rows, Iterable) or isinstance(rows, (str, bytes)):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def summarize_rows(rows: list[dict[str, Any]]) -> tuple[float, int, float, int]:
    spend = sum(as_float(row.get("spend"), 0.0) for row in rows)
    impressions = sum(as_int(row.get("impressions"), 0) for row in rows)
    clicks = sum(as_int(row.get("clicks"), 0) for row in rows)
    conversions = sum(as_int(row.get("conversions"), 0) for row in rows)
    ctr = safe_ratio(clicks, impressions)
    cpc = safe_ratio(spend, clicks)
    return spend, impressions, ctr, conversions or int(safe_ratio(clicks, 10))


__all__ = [
    "vault_get_secret",
    "http_post_compat",
    "http_get_compat",
    "resolve_url_with_default",
    "resolve_url_required",
    "resolve_secret_required",
    "stable_payload_hash",
    "normalize_rows",
    "summarize_rows",
]
