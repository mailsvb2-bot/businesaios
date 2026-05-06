from __future__ import annotations

from runtime._internal.effects_clients.http_client import http_json
from runtime._internal.http_transport import DisabledNetworkTransport


class _StubTransport(DisabledNetworkTransport):
    async def get_json(self, **kwargs):
        return type("Resp", (), {"status": 200, "json": {"ok": True, "url": kwargs.get("url")}, "text": ""})()

    async def post_json(self, **kwargs):
        return type("Resp", (), {"status": 200, "json": {"ok": True, "payload": dict(kwargs.get("data") or {})}, "text": ""})()


def test_http_json_get_routes_via_transport_without_real_network():
    out = http_json("GET", "https://example.test/ping", {"x": 1}, transport=_StubTransport())
    assert out["ok"] is True
    assert out["url"].startswith("https://example.test/ping")


def test_http_json_post_routes_via_transport_without_real_network():
    out = http_json("POST", "https://example.test/ping", {"x": 1}, transport=_StubTransport())
    assert out["ok"] is True
    assert out["payload"] == {"x": 1}
