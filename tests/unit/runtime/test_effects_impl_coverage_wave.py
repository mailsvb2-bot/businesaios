from __future__ import annotations

import http.client
import json
from types import SimpleNamespace

import pytest

from runtime._internal import _effects_impl as impl
from runtime._internal.effects_clients.yookassa_webhook_server import start_yookassa_webhook_server_in_thread


def _request(server, method, path, *, body=None, headers=None):
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=3)
    payload = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None
    request_headers = dict(headers or {})
    if payload is not None:
        request_headers.setdefault("content-type", "application/json")
        request_headers.setdefault("content-length", str(len(payload)))
    conn.request(method, path, body=payload, headers=request_headers)
    response = conn.getresponse()
    raw = response.read()
    conn.close()
    try:
        decoded = json.loads(raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        decoded = raw.decode("utf-8", errors="replace")
    return response.status, decoded


def _close(server):
    server.shutdown()
    server.server_close()


def test_http_helpers_and_network_gate(monkeypatch):
    monkeypatch.setattr(impl, "_form_body_encoder", lambda data: repr(data).encode())
    monkeypatch.setattr(impl, "_url_with_params", lambda *, url, params: f"{url}?{params['x']}")
    assert impl.encode_form_body({"a": 1}) == b"{'a': 1}"
    assert impl.url_with_params(url="u", params={"x": 2}) == "u?2"

    monkeypatch.setattr(impl, "_runtime_network_mode", lambda: "disabled")
    with pytest.raises(RuntimeError, match="network_disabled"):
        impl.http_get(url="https://example")

    monkeypatch.setattr(impl, "_runtime_network_mode", lambda: "enabled")
    monkeypatch.setattr(impl, "_sync_get", lambda **kw: ("get", kw))
    monkeypatch.setattr(impl, "_sync_post_json", lambda **kw: ("post", kw))
    assert impl.http_get(url="u", timeout_s=0)[0] == "get"
    assert impl.http_post(url="u", timeout_s=0)[0] == "post"
    assert impl.http_json("get", "u", {"b": 2}, params={"a": 1})[1]["params"] == {"a": 1, "b": 2}
    assert impl.http_json("post", "u", {"b": 2})[1]["data"] == {"b": 2}
    with pytest.raises(ValueError, match="unsupported_json_http_method"):
        impl.http_json("delete", "u")


def test_health_server_contracts():
    server = impl.start_health_server_in_thread(snapshot=object(), host="127.0.0.1", port=0)
    try:
        assert _request(server, "GET", "/missing")[0] == 404
        assert _request(server, "GET", "/health")[1]["code"] == "invalid_health_snapshot"
    finally:
        _close(server)

    class Snapshot:
        def __init__(self, value):
            self.value = value

        def collect(self):
            if isinstance(self.value, Exception):
                raise self.value
            return self.value

    server = impl.start_health_server_in_thread(snapshot=Snapshot(RuntimeError()), host="127.0.0.1", port=0)
    try:
        assert _request(server, "GET", "/readyz")[1]["code"] == "health_snapshot_failed"
    finally:
        _close(server)
    server = impl.start_health_server_in_thread(snapshot=Snapshot("ok"), host="127.0.0.1", port=0)
    try:
        assert _request(server, "GET", "/healthz")[1] == {"payload": "ok", "ok": True}
    finally:
        _close(server)


def test_telegram_webhook_server_paths_and_health():
    received = []
    server = impl.start_telegram_webhook_server_in_thread(
        host="127.0.0.1", port=0, path="/hook", on_update=received.append, secret_token="secret"
    )
    try:
        assert _request(server, "GET", "/health")[1]["name"] == "telegram-webhook"
        assert _request(server, "POST", "/wrong", body={})[0] == 404
        assert _request(server, "POST", "/hook", body={}, headers={"X-Telegram-Bot-Api-Secret-Token": "bad"})[0] == 401
        assert _request(server, "POST", "/hook", body=b"{", headers={"X-Telegram-Bot-Api-Secret-Token": "secret"})[0] == 400
        assert _request(server, "POST", "/hook", body=[], headers={"X-Telegram-Bot-Api-Secret-Token": "secret"})[1]["code"] == "invalid_update"
        assert _request(server, "POST", "/hook", body={"update_id": 1}, headers={"X-Telegram-Bot-Api-Secret-Token": "secret"})[0] == 200
        assert received == [{"update_id": 1}]
    finally:
        _close(server)

    server = impl.start_telegram_webhook_server_in_thread(
        host="127.0.0.1", port=0, path="", on_update=lambda _payload: (_ for _ in ()).throw(RuntimeError()), snapshot=SimpleNamespace(collect=lambda: "healthy")
    )
    try:
        assert _request(server, "GET", "/readyz")[1] == {"payload": "healthy", "ok": True}
        assert _request(server, "POST", "/telegram-webhook/", body={})[1]["code"] == "update_processing_failed"
    finally:
        _close(server)

    server = impl.start_telegram_webhook_server_in_thread(
        host="127.0.0.1", port=0, path="/hook", on_update=lambda _: None,
        snapshot=SimpleNamespace(collect=lambda: (_ for _ in ()).throw(RuntimeError())),
    )
    try:
        assert _request(server, "GET", "/healthz")[1]["code"] == "health_snapshot_failed"
    finally:
        _close(server)


def test_yookassa_webhook_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("YOOKASSA_WEBHOOK_AUTH_MODE", "token")
    monkeypatch.delenv("YOOKASSA_WEBHOOK_TOKEN", raising=False)
    server = start_yookassa_webhook_server_in_thread(
        host="127.0.0.1", port=0, path="/hook", event_store=None,
        payment_outbox=SimpleNamespace(enqueue_once=lambda **_: None),
    )
    try:
        status, _ = _request(server, "POST", "/hook", body={"event": "payment.succeeded", "object": {"id": "p1"}}, headers={"X-Webhook-Token": "missing"})
        assert status == 401
    finally:
        _close(server)

    monkeypatch.setenv("YOOKASSA_WEBHOOK_AUTH_MODE", "mystery")
    with pytest.raises(RuntimeError, match="YOOKASSA_WEBHOOK_AUTH_MODE unsupported"):
        start_yookassa_webhook_server_in_thread(
            host="127.0.0.1", port=0, path="/hook", event_store=None,
            payment_outbox=SimpleNamespace(enqueue_once=lambda **_: None),
        )

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("YOOKASSA_WEBHOOK_AUTH_MODE", "none")
    with pytest.raises(RuntimeError, match="not allowed in prod"):
        start_yookassa_webhook_server_in_thread(
            host="127.0.0.1", port=0, path="/hook", event_store=None,
            payment_outbox=SimpleNamespace(enqueue_once=lambda **_: None),
        )
    monkeypatch.setenv("YOOKASSA_WEBHOOK_AUTH_MODE", "token")
    monkeypatch.delenv("YOOKASSA_WEBHOOK_IP_ALLOWLIST", raising=False)
    with pytest.raises(RuntimeError, match="IP_ALLOWLIST required"):
        start_yookassa_webhook_server_in_thread(
            host="127.0.0.1", port=0, path="/hook", event_store=None,
            payment_outbox=SimpleNamespace(enqueue_once=lambda **_: None),
        )


def test_yookassa_webhook_delivery_and_persistence_errors(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("YOOKASSA_WEBHOOK_AUTH_MODE", "token")
    monkeypatch.setenv("YOOKASSA_WEBHOOK_TOKEN", "secret")
    events = []
    queued = []
    outbox = SimpleNamespace(enqueue_once=lambda **kw: queued.append(kw))
    server = start_yookassa_webhook_server_in_thread(
        host="127.0.0.1", port=0, path="/hook",
        event_store=SimpleNamespace(append=events.append), payment_outbox=outbox,
    )
    try:
        assert _request(server, "POST", "/wrong", body={})[0] == 404
        assert _request(server, "POST", "/hook", body={}, headers={"X-Webhook-Token": "bad"})[0] == 401
        assert _request(server, "POST", "/hook", body=b"{", headers={"X-Webhook-Token": "secret"}) == (400, "bad_request")
        assert _request(server, "POST", "/hook", body=[], headers={"X-Webhook-Token": "secret"}) == (400, "bad_request")
        payload = {"event": "payment.succeeded", "object": {"id": "p1"}}
        assert _request(server, "POST", "/hook", body=payload, headers={"X-Webhook-Token": "secret"}) == (200, "ok")
        assert queued[0]["dedupe_key"] == "yk:webhook:payment.succeeded:p1"
        assert queued[0]["payload"]["type"] == "yookassa_webhook"
        assert events == []  # The canonical durable outbox is authoritative; event_store is not a second path.
        assert _request(server, "POST", "/hook", body=b"x" * 1_048_577, headers={"X-Webhook-Token": "secret"})[0] == 413
    finally:
        _close(server)

    def fail_outbox(**_kwargs):
        raise RuntimeError("outbox unavailable")

    failing = start_yookassa_webhook_server_in_thread(
        host="127.0.0.1", port=0, path="/",
        event_store=None, payment_outbox=SimpleNamespace(enqueue_once=fail_outbox),
    )
    try:
        assert _request(failing, "POST", "/", body={"event": "payment.succeeded", "object": {"id": "p2"}}, headers={"X-Webhook-Token": "secret"})[0] == 503
    finally:
        _close(failing)

    with pytest.raises(RuntimeError, match="YOOKASSA_WEBHOOK_DURABLE_IDEMPOTENT_OUTBOX_REQUIRED"):
        start_yookassa_webhook_server_in_thread(
            host="127.0.0.1", port=0, path="/", event_store=None,
            payment_outbox=SimpleNamespace(enqueue=lambda payload: None),
        )

    server = start_yookassa_webhook_server_in_thread(
        host="127.0.0.1", port=0, path="/", event_store=object(),
        payment_outbox=SimpleNamespace(enqueue_once=lambda **_: None),
    )
    try:
        assert _request(server, "POST", "/", body={"event": "payment.succeeded", "object": {"id": "p3"}}, headers={"X-Webhook-Token": "secret"}) == (200, "ok")
    finally:
        _close(server)


def test_effects_initialization_and_error_emission(monkeypatch):
    transport = object()
    monkeypatch.setattr(impl, "build_http_transport", lambda: transport)
    initialized = []
    monkeypatch.setattr(impl, "initialize_effects_runtime_state", initialized.append)
    router = SimpleNamespace(transport=None, outbound_queue=None)
    effects = impl.Effects(event_log=object(), policy_registry=object(), telegram_outbound_queue="queue", effect_router=router)
    assert effects.http_transport is transport
    assert router.transport is transport
    assert router.outbound_queue == "queue"
    assert initialized == [effects]

    captured = []
    monkeypatch.setattr(impl, "throttled_emit_error", lambda **kw: captured.append(kw))
    effects._last_err_ms = {}
    effects._throttled_emit_err("key", event_type="error", payload={"x": 1})
    assert captured[0]["key"] == "key"

    created = []
    monkeypatch.setattr(impl, "EffectRouter", lambda **kw: created.append(kw) or SimpleNamespace(**kw))
    second = impl.Effects(event_log=object(), policy_registry=object(), telegram_outbound_queue="q")
    assert created[0] == {"transport": transport, "outbound_queue": "q"}
    assert second.effect_router.outbound_queue == "q"


def test_remaining_effects_impl_branches(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_BASE", " https://telegram.example/ ")
    assert impl._telegram_api_base() == "https://telegram.example"

    health = impl.start_health_server_in_thread(
        snapshot=SimpleNamespace(collect=lambda: {"status": "ready"}),
        host="127.0.0.1",
        port=0,
    )
    try:
        assert _request(health, "GET", "/health")[1] == {
            "status": "ready",
            "ok": True,
        }
    finally:
        _close(health)

    telegram = impl.start_telegram_webhook_server_in_thread(
        host="127.0.0.1",
        port=0,
        path="/hook",
        on_update=lambda _: None,
        snapshot=SimpleNamespace(collect=lambda: {"status": "ready"}),
    )
    try:
        assert _request(telegram, "GET", "/missing")[0] == 404
        assert _request(telegram, "GET", "/health")[1] == {
            "status": "ready",
            "ok": True,
        }
    finally:
        _close(telegram)

    monkeypatch.setenv("YOOKASSA_WEBHOOK_AUTH_MODE", "token")
    monkeypatch.setenv("YOOKASSA_WEBHOOK_TOKEN", "secret")
    no_event_method = start_yookassa_webhook_server_in_thread(
        host="127.0.0.1",
        port=0,
        path="/",
        event_store=object(),
        payment_outbox=SimpleNamespace(enqueue_once=lambda **_: None),
    )
    try:
        assert _request(no_event_method, "POST", "/", body={"id": "x"}, headers={"X-Webhook-Token": "secret"})[0] == 200
    finally:
        _close(no_event_method)

    preset_transport = object()
    preset_router = SimpleNamespace(transport=object(), outbound_queue="existing")
    initialized = []
    monkeypatch.setattr(impl, "initialize_effects_runtime_state", initialized.append)
    effects = impl.Effects(
        event_log=object(),
        policy_registry=object(),
        http_transport=preset_transport,
        effect_router=preset_router,
        telegram_outbound_queue="new",
    )
    assert effects.http_transport is preset_transport
    assert preset_router.outbound_queue == "existing"
    assert initialized == [effects]


def test_sealed_llm_router_uses_canonical_tenant_store_and_rejects_rebinding():
    from core.events.log import EventLog
    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    store = MemoryEventStore()
    effects = impl.Effects(event_log=EventLog(store, tenant="tenant-a"), policy_registry=object(), event_store=store)
    assert effects.effect_router.llm_accounting_store is store
    assert effects.effect_router.llm_tenant_id == "tenant-a"
    with pytest.raises(RuntimeError, match="llm_effect_router_tenant_mismatch"):
        impl.Effects(event_log=EventLog(store, tenant="tenant-b"), policy_registry=object(),
                     event_store=store, effect_router=effects.effect_router)
    assert effects.effect_router.llm_tenant_id == "tenant-a"
