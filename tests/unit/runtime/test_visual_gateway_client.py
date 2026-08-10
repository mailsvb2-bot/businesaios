from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from runtime._internal import http_transport
from runtime._internal.effects_clients.visual_gateway_client import visual_gateway_json
from runtime._internal.http_transport import HTTPResponse, HttpTransport, same_origin_url


@dataclass
class _RecordingTransport(HttpTransport):
    response: HTTPResponse
    method: str = ""
    url: str = ""
    headers: dict[str, str] | None = None
    payload: dict[str, Any] | None = None

    async def post_json(self, *, url: str, headers=None, data=None, timeout_s: int = 30) -> HTTPResponse:
        self.method = "POST"
        self.url = url
        self.headers = dict(headers or {})
        self.payload = dict(data or {})
        return self.response

    async def get_json(self, *, url: str, headers=None, params=None, timeout_s: int = 30) -> HTTPResponse:
        self.method = "GET"
        self.url = url
        self.headers = dict(headers or {})
        self.payload = dict(params or {})
        return self.response


def test_visual_gateway_client_uses_bearer_auth_and_sealed_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISUAL_GATEWAY_URL", "https://visual-gateway.example/")
    monkeypatch.setenv("VISUAL_GATEWAY_TOKEN", "secret-token")
    transport = _RecordingTransport(HTTPResponse(status=200, json={"id": "j1"}, text=""))

    assert visual_gateway_json(
        "POST",
        "/v1/creative/generations",
        {"scope_id": "tenant-1"},
        transport=transport,
    ) == {"id": "j1"}
    assert transport.method == "POST"
    assert transport.url == "https://visual-gateway.example/v1/creative/generations"
    assert transport.headers == {"Accept": "application/json", "Authorization": "Bearer secret-token"}
    assert transport.payload == {"scope_id": "tenant-1"}


def test_visual_gateway_client_rejects_http_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISUAL_GATEWAY_URL", "https://visual-gateway.example")
    monkeypatch.setenv("VISUAL_GATEWAY_TOKEN", "secret-token")
    transport = _RecordingTransport(HTTPResponse(status=503, json={"detail": "down"}, text=""))
    with pytest.raises(RuntimeError, match="visual_gateway_http_503"):
        visual_gateway_json("GET", "/v1/creative/generations/j1", {"scope_id": "tenant-1"}, transport=transport)


def test_authenticated_redirect_policy_is_same_origin_only(monkeypatch: pytest.MonkeyPatch) -> None:
    assert same_origin_url("https://visual.example/start", "https://visual.example/next")
    assert not same_origin_url("https://visual.example/start", "https://other.example/next")
    assert not same_origin_url("https://visual.example/start", "http://visual.example/next")

    captured: dict[str, Any] = {}

    class _RedirectHandler:
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return "followed"

    class _RequestModule:
        HTTPRedirectHandler = _RedirectHandler

        @staticmethod
        def build_opener(handler):
            captured["handler"] = handler
            return SimpleNamespace(open=lambda *_args, **_kwargs: None)

    monkeypatch.setattr(http_transport, "_urllib_request", lambda: _RequestModule)
    http_transport._authenticated_urlopen("https://visual.example/start")
    handler = captured["handler"]
    assert handler.redirect_request(None, None, 302, "redirect", {}, "https://visual.example/next") == "followed"
    with pytest.raises(Exception, match="cross_origin_redirect_blocked"):
        handler.redirect_request(None, None, 302, "redirect", {}, "https://other.example/next")
