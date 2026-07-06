from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .base import AdsConnectorError, AdsPlatform
from .connector_value_coercion import as_float, as_int, safe_ratio
from .connector_value_coercion import as_optional_float as as_optional_float
from .connector_value_coercion import as_optional_int as as_optional_int


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
    if isinstance(value, list | tuple):
        return [_stable_jsonable(v) for v in value]
    if isinstance(value, set):
        return sorted(_stable_jsonable(v) for v in value)
    return value


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
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


def _first_present(raw: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = raw.get(key)
        if value not in (None, "", [], ()):  # keep 0 valid
            return value
    return None


def _first_scalar(value: Any) -> str:
    if isinstance(value, Mapping):
        for candidate in ("id", "account_id", "customer_id", "advertiser_id"):
            found = value.get(candidate)
            if found not in (None, "", [], ()):  # keep 0 valid
                return str(found).strip()
        return ""
    if isinstance(value, list | tuple | set):
        values = [str(item).strip() for item in value if str(item).strip()]
        if len(values) == 1:
            return values[0]
        return ""
    return str(value).strip() if value not in (None, "") else ""


def pending_account_id_from_raw(
    *,
    tenant_id: str,
    raw: Mapping[str, Any],
    candidate_keys: Sequence[str],
    pending_prefix: str,
) -> str:
    payload = dict(raw or {})
    value = _first_present(payload, candidate_keys)
    if value is None and isinstance(payload.get("data"), Mapping):
        value = _first_present(payload["data"], candidate_keys)
    scalar = _first_scalar(value)
    if scalar:
        return scalar
    return f"{str(pending_prefix).strip()}:{str(tenant_id).strip() or 'default'}"


async def tokens_put_compat(
    *,
    tokens: Any,
    tenant_id: str,
    platform: AdsPlatform,
    account_id: str,
    access_token: str,
    scope: str,
    connector_name: str,
) -> None:
    if tokens is None:
        raise AdsConnectorError(f"{connector_name}: token store is not configured")
    payload = {
        "tenant_id": str(tenant_id),
        "platform": str(platform.value),
        "account_id": str(account_id),
        "access_token": str(access_token),
        "scope": str(scope),
    }
    for method_name in ("put_token", "put", "save", "set", "store"):
        method = getattr(tokens, method_name, None)
        if not callable(method):
            continue
        try:
            await _maybe_await(method(**payload))
            return
        except TypeError:
            try:
                await _maybe_await(method(str(tenant_id), str(platform.value), str(account_id), str(access_token), str(scope)))
                return
            except TypeError:
                continue
    raise AdsConnectorError(f"{connector_name}: token store must expose put_token/put/save/set/store")


async def tokens_get_access_token_compat(
    *,
    tokens: Any,
    tenant_id: str,
    platform: AdsPlatform,
    account_id: str,
) -> str:
    if tokens is None:
        raise AdsConnectorError("connector token store is not configured")
    payload = {
        "tenant_id": str(tenant_id),
        "platform": str(platform.value),
        "account_id": str(account_id),
    }
    for method_name in ("get_access_token", "access_token", "get_token", "get", "load"):
        method = getattr(tokens, method_name, None)
        if not callable(method):
            continue
        try:
            value = await _maybe_await(method(**payload))
        except TypeError:
            try:
                value = await _maybe_await(method(str(tenant_id), str(platform.value), str(account_id)))
            except TypeError:
                continue
        if isinstance(value, Mapping):
            value = value.get("access_token") or value.get("token")
        token = _normalize_secret_value(value)
        if token:
            return token
    raise AdsConnectorError("connector token store returned no access_token")


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
    if not isinstance(rows, Iterable) or isinstance(rows, str | bytes):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def summarize_rows(rows: list[dict[str, Any]]) -> tuple[float, int, float, int]:
    spend = sum(as_float(row.get("spend"), 0.0) for row in rows)
    impressions = sum(as_int(row.get("impressions"), 0) for row in rows)
    clicks = sum(as_int(row.get("clicks"), 0) for row in rows)
    conversions = sum(as_int(row.get("conversions"), 0) for row in rows)
    ctr = safe_ratio(clicks, impressions)
    return spend, impressions, ctr, conversions or int(safe_ratio(clicks, 10))


__all__ = [
    "vault_get_secret",
    "pending_account_id_from_raw",
    "tokens_put_compat",
    "tokens_get_access_token_compat",
    "http_post_compat",
    "http_get_compat",
    "resolve_url_with_default",
    "resolve_url_required",
    "resolve_secret_required",
    "stable_payload_hash",
    "normalize_rows",
    "summarize_rows",
]
