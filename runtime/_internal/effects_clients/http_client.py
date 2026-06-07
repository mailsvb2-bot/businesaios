from __future__ import annotations

"""Sealed transport: minimal HTTP/URL helpers.

This module is *internal* to runtime/_internal. It centralizes urllib usage so that
network access stays sealed.

IMPORTANT:
- Keep behavior identical to prior runtime/_internal/_effects_impl.py helpers.
- Do not introduce alternative logic paths.
"""

import json
import logging
import threading
from typing import Any, Optional

from runtime._internal.http_transport import HttpTransport, build_http_transport
from runtime._internal.http_transport import url_with_params as _canonical_url_with_params
from runtime.observability.error_handling import swallow

logger = logging.getLogger(__name__)


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


def _url_with_params(url: str, params: dict[str, Any] | None) -> str:
    return _canonical_url_with_params(url=str(url), params=params)


def url_with_params(*, url: str, params: dict[str, Any] | None = None) -> str:
    """Backward-compatible export that delegates to canonical transport helper."""
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
