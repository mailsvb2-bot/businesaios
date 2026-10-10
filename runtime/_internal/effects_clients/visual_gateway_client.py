from __future__ import annotations

from typing import Any

from runtime._internal.effects_clients.http_client import _run_coroutine_sync
from runtime._internal.http_transport import HTTPBytesResponse, HttpTransport, build_http_transport
from runtime.platform.config.env_flags import env_bool, env_str


def _gateway_config() -> tuple[str, dict[str, str]]:
    base_url = env_str("VISUAL_GATEWAY_URL", "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("visual_gateway_not_configured")
    token = env_str("VISUAL_GATEWAY_TOKEN", "").strip()
    if not token and not env_bool("VISUAL_GATEWAY_ALLOW_ANONYMOUS", False):
        raise RuntimeError("visual_gateway_token_not_configured")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return base_url, headers


def visual_gateway_json(method: str, path: str, payload: dict[str, Any] | None, *, timeout_s: int = 30, transport: HttpTransport | None = None) -> dict[str, Any]:
    method = str(method or "GET").strip().upper()
    if method not in {"GET", "POST"}:
        raise ValueError(f"unsupported_visual_gateway_method:{method}")
    base_url, headers = _gateway_config()
    target = base_url + "/" + str(path or "").lstrip("/")
    active = transport or build_http_transport()
    timeout = max(3, min(int(timeout_s or 30), 300))

    async def _call():
        if method == "GET":
            return await active.get_json(url=target, headers=headers, params=dict(payload or {}), timeout_s=timeout)
        return await active.post_json(url=target, headers=headers, data=dict(payload or {}), timeout_s=timeout)

    response = _run_coroutine_sync(_call())
    status, body = int(getattr(response, "status", 0) or 0), getattr(response, "json", None)
    if not 200 <= status < 300 or not isinstance(body, dict):
        raise RuntimeError(f"visual_gateway_http_{status}")
    return dict(body)


def visual_gateway_bytes(
    path: str,
    params: dict[str, Any] | None,
    *,
    timeout_s: int = 60,
    max_bytes: int = 256 * 1024 * 1024,
    transport: HttpTransport | None = None,
) -> tuple[bytes, str]:
    base_url, headers = _gateway_config()
    target = base_url + "/" + str(path or "").lstrip("/")
    active = transport or build_http_transport()
    timeout = max(3, min(int(timeout_s or 60), 300))
    limit = max(1, min(int(max_bytes), 512 * 1024 * 1024))

    async def _call() -> HTTPBytesResponse:
        return await active.get_bytes(
            url=target,
            headers=headers,
            params=dict(params or {}),
            timeout_s=timeout,
            max_bytes=limit,
        )

    response = _run_coroutine_sync(_call())
    if not 200 <= int(response.status or 0) < 300 or not response.body:
        raise RuntimeError(f"visual_gateway_http_{int(response.status or 0)}")
    mime = str(
        response.headers.get("Content-Type")
        or response.headers.get("content-type")
        or "application/octet-stream"
    ).split(";", 1)[0].strip().lower()
    if not mime or len(mime) > 120 or any(ord(ch) < 32 for ch in mime):
        raise RuntimeError("visual_gateway_invalid_content_type")
    return bytes(response.body), mime


__all__ = ["visual_gateway_bytes", "visual_gateway_json"]
