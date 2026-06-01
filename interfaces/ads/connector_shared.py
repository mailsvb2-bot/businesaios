from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping, Optional

from .base import AdsConnectorError, AdsPlatform
from .connector_value_coercion import (
    as_float,
    as_int,
    as_optional_float,
    as_optional_int,
    safe_ratio,
)


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
    request = getattr(http, "request", None)
    if not callable(request):
        raise AdsConnectorError("connector http client must implement post() or request()")
    return _normalized_mapping(await request(
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
    request = getattr(http, "request", None)
    if not callable(request):
        raise AdsConnectorError("connector http client must implement get() or request()")
    return _normalized_mapping(await request(
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
    return str(value)


def pending_account_id_from_raw(
    *,
    tenant_id: str,
    raw: Mapping[str, Any],
    candidate_keys: Iterable[str],
    pending_prefix: str,
) -> str:
    for key in candidate_keys:
        value = raw.get(key)
        if isinstance(value, list) and value:
            value = value[0]
        if value is not None:
            account_id = str(value).strip()
            if account_id:
                return account_id

        data = raw.get("data")
        if isinstance(data, Mapping):
            nested_value = data.get(key)
            if isinstance(nested_value, list) and nested_value:
                nested_value = nested_value[0]
            if nested_value is not None:
                nested_account_id = str(nested_value).strip()
                if nested_account_id:
                    return nested_account_id

    stable_payload = json.dumps(_stable_jsonable(raw), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(
        f"{tenant_id}|{stable_payload}".encode("utf-8", errors="ignore")
    ).hexdigest()[:12]
    return f"{pending_prefix}:{digest}"


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
    put = getattr(tokens, "put", None)
    if callable(put):
        await put(
            tenant_id=tenant_id,
            platform=platform,
            account_id=account_id,
            token={
                "access_token": access_token,
                "scope": scope,
                "expires_at_iso": None,
            },
        )
        return
    upsert = getattr(tokens, "upsert", None)
    if callable(upsert):
        await upsert(
            tenant_id=tenant_id,
            platform=str(platform.value),
            account_id=account_id,
            access_token=access_token,
            refresh_token=None,
            expires_at_iso=None,
        )
        return
    raise AdsConnectorError(
        f"{connector_name}: tokens store does not support put/upsert"
    )


async def tokens_get_access_token_compat(
    *,
    tokens: Any,
    tenant_id: str,
    platform: AdsPlatform,
    account_id: str,
) -> str:
    get = getattr(tokens, "get", None)
    if callable(get):
        try:
            token = await get(
                tenant_id=tenant_id,
                platform=platform,
                account_id=account_id,
            )
        except TypeError:
            token = await get(
                tenant_id=tenant_id,
                platform=str(platform.value),
                account_id=account_id,
            )
        if token is None:
            raise AdsConnectorError(
                "Not connected: missing OAuth token for this account."
            )
        if isinstance(token, Mapping) and token.get("access_token"):
            return str(token["access_token"])
        access_token = getattr(token, "access_token", None)
        normalized = _normalize_secret_value(access_token)
        if normalized is not None:
            return normalized
    raise AdsConnectorError("Not connected: missing OAuth token for this account.")
