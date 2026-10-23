from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from interfaces.ucr import gateway as g
from runtime._internal.effects_clients.ucr_gateway_transport import SyncRequestUcrGatewayTransport

TOKEN = "t" * 40


class _Fake(BaseHTTPRequestHandler):
    seen: list[dict] = []
    mode = "ok"

    def log_message(self, *a):  # quiet
        pass

    def _reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        _Fake.seen.append({"path": self.path, "headers": dict(self.headers)})
        self._reply(200, {"ok": True, "ucr_revision": g.UCR_PINNED_REVISION})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Fake.seen.append({"path": self.path, "headers": dict(self.headers), "body": req})
        if _Fake.mode == "reject":
            return self._reply(409, {"ok": False, "error": "conflict"})
        if _Fake.mode == "busy":
            return self._reply(503, {"ok": False, "error": "retry_later"})
        rev = "0" * 40 if _Fake.mode == "badrev" else g.UCR_PINNED_REVISION
        self._reply(
            200,
            {
                "ok": True,
                "ucr_revision": rev,
                "service": req["service"],
                "method": req["method"],
                "result": {"echo": req["request"]},
            },
        )


@pytest.fixture
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _Fake.seen.clear()
    _Fake.mode = "ok"
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _client(url):
    env = {"BUSINESAIOS_UCR_GATEWAY_ENABLED": "1", "BUSINESAIOS_UCR_GATEWAY_URL": url}
    return g.UcrGatewayClient(
        config=g.ucr_gateway_config(env),
        credential_provider=g.EnvironmentCredentialProvider({"BUSINESAIOS_UCR_GATEWAY_TOKEN": TOKEN}),
        transport=SyncRequestUcrGatewayTransport(),
    )


def test_health_and_rpc_roundtrip_with_headers(server) -> None:
    c = _client(server)
    assert asyncio.run(c.health())["ok"] is True
    out = asyncio.run(
        c.invoke_universal_conference(
            method=g.UcrUniversalConferenceMethod.CREATE_CONFERENCE,
            request={"title": "Встреча"},
            idempotency_key="conf:slot-123",
        )
    )
    assert out["result"] == {"echo": {"title": "Встреча"}}
    post = _Fake.seen[-1]
    assert post["path"] == "/v1/rpc" and post["body"]["version"] == 1
    assert (
        post["headers"]["Authorization"] == f"Bearer {TOKEN}" and post["headers"]["Idempotency-Key"] == "conf:slot-123"
    )


def test_idempotency_rules(server) -> None:
    c = _client(server)
    with pytest.raises(ValueError):
        asyncio.run(c.invoke_call(method=g.UcrCallMethod.START_CALL, request={"a": 1}))
    with pytest.raises(ValueError):
        asyncio.run(c.invoke_call(method=g.UcrCallMethod.GET_CALL, request={"a": 1}, idempotency_key="key:12345678"))
    assert asyncio.run(c.invoke_call(method=g.UcrCallMethod.GET_CALL, request={"a": 1}))["ok"]


@pytest.mark.parametrize(
    ("mode", "exc"),
    [("reject", g.UcrGatewayRejected), ("busy", g.UcrGatewayUnavailable), ("badrev", g.UcrGatewayProtocolError)],
)
def test_fail_closed_error_mapping(server, mode, exc) -> None:
    _Fake.mode = mode
    with pytest.raises(exc):
        asyncio.run(_client(server).invoke_integration(method=g.UcrIntegrationMethod.GET_IDENTITY, request={"id": "x"}))


def test_config_guards() -> None:
    with pytest.raises(g.UcrGatewayConfigurationError):
        g.ucr_gateway_config(
            {"BUSINESAIOS_UCR_GATEWAY_ENABLED": "1", "BUSINESAIOS_UCR_GATEWAY_URL": "http://example.ru"}
        )
    with pytest.raises(g.UcrGatewayConfigurationError):
        g.ucr_gateway_config({"BUSINESAIOS_UCR_GATEWAY_ENABLED": "1"})
    disabled = g.UcrGatewayClient(
        config=g.ucr_gateway_config({}), credential_provider=g.EnvironmentCredentialProvider({})
    )
    with pytest.raises(g.UcrGatewayConfigurationError):
        asyncio.run(disabled.health())
    short = g.UcrGatewayClient(
        config=g.ucr_gateway_config(
            {"BUSINESAIOS_UCR_GATEWAY_ENABLED": "1", "BUSINESAIOS_UCR_GATEWAY_URL": "http://127.0.0.1:9"}
        ),
        credential_provider=g.EnvironmentCredentialProvider({"BUSINESAIOS_UCR_GATEWAY_TOKEN": "short"}),
        transport=SyncRequestUcrGatewayTransport(),
    )
    with pytest.raises(g.UcrGatewayUnavailable):
        asyncio.run(short.health())


def test_transport_must_be_injected() -> None:
    with pytest.raises(g.UcrGatewayConfigurationError):
        g.UcrGatewayClient(config=g.ucr_gateway_config({}), credential_provider=g.EnvironmentCredentialProvider({}))
