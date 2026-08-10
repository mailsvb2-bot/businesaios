from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from runtime._internal.effects_clients.visual_gateway_client import visual_gateway_json
from runtime._internal.http_transport import HTTPResponse, HttpTransport


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
