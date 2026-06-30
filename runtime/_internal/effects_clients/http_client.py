"""Sealed transport: minimal HTTP/URL helpers.

This module is *internal* to runtime/_internal. It centralizes urllib usage so that
network access stays sealed.

IMPORTANT:
- Keep behavior identical to prior runtime/_internal/_effects_impl.py helpers.
- Do not introduce alternative logic paths.
"""

from __future__ import annotations


import importlib
import json
import logging
import threading
from collections.abc import Iterable, Mapping
from typing import Any

from runtime._internal.http_transport import HttpTransport, build_http_transport

logger = logging.getLogger(__name__)


def _urllib_parse():
    return importlib.import_module("urllib.parse")


def safe_result(obj: Any) -> Any:
    """Avoid huge/unsafe payloads in event log."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in {"url", "id", "type", "status", "paid", "confirmation_url"}:
                out[k] = v
        return out
    return str(obj)[:200]


def _query_items(params: Mapping[str, Any] | None) -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    for key, value in dict(params or {}).items():
        if value is None:
            continue
        name = str(key)
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray, Mapping)):
            for item in value:
                if item is not None:
                    items.append((name, item))
            continue
        items.append((name, value))
    return items


def _url_with_params(url: str, params: Mapping[str, Any] | None) -> str:
    normalized = str(url or "").strip()
    if not normalized:
        raise ValueError("url_required")
    items = _query_items(params)
    if not items:
        return normalized
    joiner = "&" if "?" in normalized else "?"
    return normalized + joiner + _urllib_parse().urlencode(items, doseq=True)


def url_with_params(*, url: str, params: Mapping[str, Any] | None = None) -> str:
    """Backward-compatible export for sealed URL construction."""
    return _url_with_params(str(url), params)


def _run_coroutine_sync(coro):
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}
    error: list[BaseException] = []

    def _runner() -> None:
        import asyncio as _asyncio
        try:
            result['value'] = _asyncio.run(coro)
        except BaseException as exc:  # pragma: no cover - re-raised in caller
            error.append(exc)

    thread = threading.Thread(target=_runner, name='runtime-http-json-sync-bridge', daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result.get('value')


def http_json(
    method: str,
    url: str,
    params: dict[str, Any] | None,
    *,
    headers: dict[str, str] | None = None,
    timeout_s: int = 20,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    """HTTP JSON helper for runtime effects (single-module policy)."""
    params = params or {}
    headers = headers or {}
    method = str(method or '').upper().strip()
    if method not in {'GET', 'POST'}:
        raise ValueError('unsupported_http_method')
    if not str(url or '').strip():
        raise ValueError('url_required')
    timeout_s = int(timeout_s or 20)
    timeout_s = max(3, min(120, timeout_s))

    final_url = str(url)
    if method == 'GET' and params:
        final_url = _url_with_params(final_url, params)
    elif params:
        headers = {**headers, 'Content-Type': 'application/json'}

    active_transport = transport or build_http_transport()

    async def _call_via_transport() -> dict[str, Any]:
        if method == 'GET':
            resp = await active_transport.get_json(
                url=final_url,
                headers=headers,
                params=None,
                timeout_s=timeout_s,
            )
        else:
            resp = await active_transport.post_json(
                url=final_url,
                headers=headers,
                data=params if isinstance(params, dict) else {},
                timeout_s=timeout_s,
            )
        payload = resp.json
        if isinstance(payload, dict):
            return payload
        if payload is not None:
            return {'result': payload}
        if resp.text:
            try:
                parsed = json.loads(resp.text)
                return parsed if isinstance(parsed, dict) else {'result': parsed}
            except Exception:
                return {'result': resp.text}
        return {}

    return _run_coroutine_sync(_call_via_transport())
