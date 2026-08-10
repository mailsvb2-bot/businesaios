from __future__ import annotations

from typing import Any

from runtime._internal.effects_clients.http_client import _run_coroutine_sync
from runtime._internal.http_transport import HttpTransport, build_http_transport
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


def visual_gateway_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None,
    *,
    timeout_s: int = 30,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    """Call the operator-controlled visual gateway through the sealed transport."""

    normalized_method = str(method or "GET").strip().upper()
    if normalized_method not in {"GET", "POST"}:
        raise ValueError(f"unsupported_visual_gateway_method:{normalized_method}")
    base_url, headers = _gateway_config()
    relative = "/" + str(path or "").lstrip("/")
    active_transport = transport or build_http_transport()
    bounded_timeout = max(3, min(int(timeout_s or 30), 300))

    async def _call():
        if normalized_method == "GET":
            return await active_transport.get_json(
                url=base_url + relative,
                headers=headers,
                params=dict(payload or {}),
                timeout_s=bounded_timeout,
            )
        return await active_transport.post_json(
            url=base_url + relative,
            headers=headers,
            data=dict(payload or {}),
            timeout_s=bounded_timeout,
        )

    response = _run_coroutine_sync(_call())
    status = int(getattr(response, "status", 0) or 0)
    body = getattr(response, "json", None)
    if not (200 <= status < 300) or not isinstance(body, dict):
        raise RuntimeError(f"visual_gateway_http_{status}")
    return dict(body)


__all__ = ["visual_gateway_json"]
