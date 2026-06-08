from __future__ import annotations

"""Sealed transport helpers extracted from ``runtime._internal._effects_impl``."""
from typing import Any

from runtime._internal.http_transport import HTTPResponse, sync_get, sync_post_json
from runtime._internal.http_transport import url_with_params as _url_with_params


def url_with_params(*, url: str, params: dict[str, Any] | None = None) -> str:
    return _url_with_params(url=str(url), params=(params if isinstance(params, dict) else None))
async def http_get(*, url: str, headers: dict[str, str], params: dict | None = None, timeout_s: int = 30) -> HTTPResponse:
    import asyncio
    return await asyncio.to_thread(
        sync_get,
        url=str(url),
        headers=headers,
        params=params,
        timeout_s=int(timeout_s or 30),
    )
async def http_post(*, url: str, headers: dict[str, str], data: dict | None = None, timeout_s: int = 30) -> HTTPResponse:
    import asyncio
    return await asyncio.to_thread(
        sync_post_json,
        url=str(url),
        headers=headers,
        data=data,
        timeout_s=int(timeout_s or 30),
    )
__all__ = ["HTTPResponse", "http_get", "http_post", "url_with_params"]
