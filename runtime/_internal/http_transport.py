from __future__ import annotations

import importlib
import json as _json
import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4


def _socket_module():
    return importlib.import_module("socket")


def _urllib_error():
    return importlib.import_module("urllib.error")


def _urllib_parse():
    return importlib.import_module("urllib.parse")


def _urllib_request():
    return importlib.import_module("urllib.request")


def _http_client():
    return importlib.import_module("http.client")


def _ipaddress_module():
    return importlib.import_module("ipaddress")


def _mimetypes_module():
    return importlib.import_module("mimetypes")


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

    async def post_multipart_file(
        self,
        *,
        url: str,
        path: str | Path,
        field_name: str,
        fields: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout_s: int = 120,
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

def _url_origin(url: str) -> tuple[str, str, int]:
    parsed = _urllib_parse().urlsplit(_normalized_url(url))
    scheme = str(parsed.scheme).lower()
    port = int(parsed.port or (443 if scheme == "https" else 80))
    return scheme, str(parsed.hostname or "").lower(), port


def same_origin_url(source_url: str, target_url: str) -> bool:
    return _url_origin(source_url) == _url_origin(target_url)


def _authenticated_urlopen(source_url: str) -> Callable[..., object]:
    request_module = _urllib_request()
    error_module = _urllib_error()

    class _SameOriginRedirectHandler(request_module.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not same_origin_url(source_url, str(newurl)):
                raise error_module.HTTPError(newurl, code, "cross_origin_redirect_blocked", headers, fp)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    return request_module.build_opener(_SameOriginRedirectHandler()).open


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
    has_authorization = any(str(key).lower() == "authorization" for key in hdrs)
    open_call = opener or (_authenticated_urlopen(str(url)) if has_authorization else _urllib_request().urlopen)
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

    async def post_multipart_file(self, **_: Any) -> HTTPResponse:
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

    async def post_multipart_file(
        self,
        *,
        url: str,
        path: str | Path,
        field_name: str,
        fields: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout_s: int = 120,
    ) -> HTTPResponse:
        import asyncio

        result = await asyncio.to_thread(
            sync_multipart_file,
            url=str(url),
            path=path,
            field_name=str(field_name),
            fields=dict(fields or {}),
            headers=dict(headers or {}),
            timeout_s=float(timeout_s or 120),
        )
        return HTTPResponse(status=int(result.status or 0), json=result.json, text=result.text)

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
        if isinstance(value, Iterable) and not isinstance(value, str | bytes | bytearray | Mapping):
            for item in value:
                if item is not None:
                    items.append((name, item))
            continue
        items.append((name, value))
    return items

def quote_path_segment(value: object) -> str:
    """Percent-encode one URL path segment inside the sealed network boundary."""
    text = str(value or "").strip()
    if not text:
        raise ValueError("path_segment_required")
    return _urllib_parse().quote(text, safe="")


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


def _upload_target(url: str) -> tuple[object, str]:
    parsed = _urllib_parse().urlsplit(_normalized_url(url))
    if str(parsed.scheme).lower() != "https":
        raise ValueError("multipart_https_required")
    if parsed.username or parsed.password:
        raise ValueError("multipart_url_credentials_forbidden")
    host = str(parsed.hostname or "").strip().rstrip(".").lower()
    if not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".lan")):
        raise ValueError("multipart_public_host_required")
    try:
        literal = _ipaddress_module().ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise ValueError("multipart_private_ip_forbidden")
    if str(os.environ.get("APP_ENV", "dev")).strip().lower() in {"prod", "production", "stage", "staging"} and literal is None:
        addresses = {item[4][0] for item in _socket_module().getaddrinfo(host, parsed.port or 443, type=_socket_module().SOCK_STREAM)}
        if not addresses or any(not _ipaddress_module().ip_address(address).is_global for address in addresses):
            raise ValueError("multipart_non_public_dns_target")
    target = _urllib_parse().urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    return parsed, target



def validate_public_https_url(url: str) -> str:
    parsed, _ = _upload_target(str(url))
    return _urllib_parse().urlunsplit(parsed)


def sync_multipart_file(
    *,
    url: str,
    path: str | Path,
    field_name: str,
    fields: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout_s: float = 120,
    max_bytes: int = 256_000_000,
) -> SyncHTTPResult:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    size = source.stat().st_size
    if size < 0 or size > max(1, int(max_bytes)):
        raise ValueError("multipart_file_too_large")
    parsed, target = _upload_target(str(url))
    safe_field = str(field_name or "file").replace('"', "_").replace("\r", "_").replace("\n", "_")
    safe_filename = source.name.replace('"', "_").replace("\r", "_").replace("\n", "_")
    boundary = f"----BusinessAIOSBoundary{uuid4().hex}"
    chunks: list[bytes] = []
    for key, value in dict(fields or {}).items():
        safe_key = str(key).replace('"', "_").replace("\r", "_").replace("\n", "_")
        chunks.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"{safe_key}\"\r\n\r\n{value}\r\n").encode())
    mime_type = _mimetypes_module().guess_type(source.name)[0] or "application/octet-stream"
    head = b"".join(chunks) + (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{safe_field}\"; filename=\"{safe_filename}\"\r\nContent-Type: {mime_type}\r\n\r\n").encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    request_headers = {str(k): str(v) for k, v in dict(headers or {}).items()}
    request_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    request_headers["Content-Length"] = str(len(head) + size + len(tail))
    connection = _http_client().HTTPSConnection(str(parsed.hostname), parsed.port or 443, timeout=float(timeout_s))
    try:
        connection.putrequest("POST", target)
        for key, value in request_headers.items():
            connection.putheader(key, value)
        connection.endheaders()
        connection.send(head)
        with source.open("rb") as handle:
            while chunk := handle.read(256 * 1024):
                connection.send(chunk)
        connection.send(tail)
        response = connection.getresponse()
        raw = response.read()
        text = raw.decode("utf-8", errors="replace") if raw else ""
        try:
            parsed_json = _json.loads(text) if text else None
        except Exception:
            parsed_json = None
        response_headers = {str(k): str(v) for k, v in response.getheaders()}
        status = int(response.status or 0)
        return SyncHTTPResult(status=status, headers=response_headers, json=parsed_json, text=text, error_kind=None if 200 <= status < 300 else "http_error", error_message=None if 200 <= status < 300 else f"HTTP {status}")
    finally:
        connection.close()

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
    "quote_path_segment",
    "runtime_network_mode",
    "same_origin_url",
    "sync_get",
    "sync_multipart_file",
    "sync_post_json",
    "sync_request",
    "url_with_params",
    "validate_public_https_url",
]
