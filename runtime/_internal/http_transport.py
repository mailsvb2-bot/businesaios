from __future__ import annotations

import importlib
import json as _json
import os
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable, Iterable, Mapping


def _socket_module():
    return importlib.import_module("socket")


def _urllib_error():
    return importlib.import_module("urllib.error")


def _urllib_parse():
    return importlib.import_module("urllib.parse")


def _urllib_request():
    return importlib.import_module("urllib.request")


def runtime_network_mode() -> str:
    enabled = str(os.environ.get("BUSINESAIOS_ALLOW_NETWORK", "0")).strip().lower() in {"1", "true", "yes", "on"}
    return "enabled" if enabled else "disabled"


@dataclass(frozen=True)
class HTTPResponse:
    status: int
    json: Any | None
    text: str

class HttpTransport:
    async def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        timeout_s: int = 30,
    ) -> HTTPResponse:
        raise NotImplementedError

    async def get_json(
        self,
        *,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout_s: int = 30,
    ) -> HTTPResponse:
        raise NotImplementedError

@dataclass(frozen=True)
class SyncHTTPResult:
    status: int | None
    headers: dict[str, str]
    json: Any | None
    text: str
    error_kind: str | None = None
    error_message: str | None = None

def sync_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout_s: float = 30,
    opener: Callable[..., object] | None = None,
) -> SyncHTTPResult:
    hdrs = dict(headers or {})
    req = _urllib_request().Request(
        url=_normalized_url(str(url)),
        data=body,
        headers=hdrs,
        method=str(method or "GET").upper(),
    )
    open_call = opener or _urllib_request().urlopen
    try:
        with open_call(req, timeout=timeout_s) as resp:
            decoded = _decode_response(resp)
            response_headers = {}
            try:
                response_headers = {str(k): str(v) for k, v in resp.headers.items()}
            except Exception:
                response_headers = {}
            return SyncHTTPResult(
                status=decoded.status,
                headers=response_headers,
                json=decoded.json,
                text=decoded.text,
            )
    except _urllib_error().HTTPError as exc:
        http_response = _response_from_http_error(exc)
        try:
            response_headers = {str(k): str(v) for k, v in exc.headers.items()}
        except Exception:
            response_headers = {}
        return SyncHTTPResult(
            status=http_response.status,
            headers=response_headers,
            json=http_response.json,
            text=http_response.text,
            error_kind="http_error",
            error_message=str(exc),
        )
    except _urllib_error().URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, _socket_module().timeout):
            return SyncHTTPResult(
                status=None,
                headers={},
                json=None,
                text="",
                error_kind="timeout",
                error_message=str(reason),
            )
        return SyncHTTPResult(
            status=None,
            headers={},
            json=None,
            text="",
            error_kind="transport_error",
            error_message=str(reason),
        )
    except _socket_module().timeout as exc:
        return SyncHTTPResult(
            status=None,
            headers={},
            json=None,
            text="",
            error_kind="timeout",
            error_message=str(exc),
        )
    except (OSError, ValueError) as exc:
        return SyncHTTPResult(
            status=None,
            headers={},
            json=None,
            text="",
            error_kind="transport_error",
            error_message=str(exc),
        )

class DisabledNetworkTransport(HttpTransport):
    async def post_json(self, **_: Any) -> HTTPResponse:
        raise RuntimeError("network_disabled_in_this_runtime")

    async def get_json(self, **_: Any) -> HTTPResponse:
        raise RuntimeError("network_disabled_in_this_runtime")

class UrllibHttpTransport(HttpTransport):
    async def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        timeout_s: int = 30,
    ) -> HTTPResponse:
        import asyncio

        return await asyncio.to_thread(
            sync_post_json,
            url=str(url),
            headers=dict(headers or {}),
            data=dict(data or {}),
            timeout_s=int(timeout_s or 30),
        )

    async def get_json(
        self,
        *,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout_s: int = 30,
    ) -> HTTPResponse:
        import asyncio

        return await asyncio.to_thread(
            sync_get,
            url=str(url),
            headers=dict(headers or {}),
            params=dict(params or {}),
            timeout_s=int(timeout_s or 30),
        )

def _normalized_url(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        raise ValueError("url_required")
    parsed = _urllib_parse().urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("absolute_http_url_required")
    return _urllib_parse().urlunsplit(parsed)

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

def url_with_params(*, url: str, params: dict[str, Any] | None = None) -> str:
    normalized = _normalized_url(str(url))
    items = _query_items(params)
    if not items:
        return normalized
    return normalized + ("&" if "?" in normalized else "?") + _urllib_parse().urlencode(items, doseq=True)

def form_urlencode(data: dict[str, Any]) -> bytes:
    """Encode x-www-form-urlencoded payloads inside the sealed HTTP layer.

    This keeps urllib usage centralized under runtime/_internal/http_transport.py
    instead of leaking URL/form helpers into runtime domain modules.
    """

    return _urllib_parse().urlencode(_query_items(data), doseq=True).encode("utf-8")

def _decode_response(resp) -> HTTPResponse:
    raw = resp.read()
    status = int(getattr(resp, "status", 200) or 200)
    txt = raw.decode("utf-8", errors="replace") if raw else ""
    try:
        js = _json.loads(txt) if txt else None
    except Exception:
        js = None
    return HTTPResponse(status=status, json=js, text=str(txt))

def _response_from_http_error(exc: Exception) -> HTTPResponse:
    body = ""
    try:
        raw = exc.read()
        body = raw.decode("utf-8", errors="replace") if raw else ""
    except Exception:
        body = str(exc)
    try:
        parsed = _json.loads(body) if body else None
    except Exception:
        parsed = None
    return HTTPResponse(status=int(getattr(exc, "code", 0) or 0), json=parsed, text=body)

def sync_post_json(*, url: str, headers: dict[str, str] | None = None, data: dict[str, Any] | None = None, timeout_s: int = 30) -> HTTPResponse:
    body = _json.dumps(dict(data or {}), ensure_ascii=False).encode("utf-8")
    result = sync_request(method="POST", url=url, headers={**dict(headers or {}), "Content-Type": "application/json"}, body=body, timeout_s=float(timeout_s or 30))
    return HTTPResponse(status=int(result.status or 0), json=result.json, text=result.text)

def sync_get(*, url: str, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None, timeout_s: int = 30) -> HTTPResponse:
    try:
        final_url = url_with_params(url=url, params=params)
    except ValueError:
        return HTTPResponse(status=599, json=None, text="")
    result = sync_request(method="GET", url=final_url, headers=dict(headers or {}), timeout_s=float(timeout_s or 30))
    return HTTPResponse(status=int(result.status or 0), json=result.json, text=result.text)

def build_http_transport(*, allow_network: bool | None = None) -> HttpTransport:
    if allow_network is None:
        allow_network = runtime_network_mode() == "enabled"
    return UrllibHttpTransport() if allow_network else DisabledNetworkTransport()

__all__ = [
    "HTTPResponse",
    "HttpTransport",
    "SyncHTTPResult",
    "DisabledNetworkTransport",
    "UrllibHttpTransport",
    "build_http_transport",
    "form_urlencode",
    "runtime_network_mode",
    "sync_get",
    "sync_post_json",
    "sync_request",
    "url_with_params",
]
