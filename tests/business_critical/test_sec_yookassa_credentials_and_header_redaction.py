"""Independent regressions for YooKassa auth, audit redaction and tenant isolation."""

from __future__ import annotations

import base64
import hmac
import http.client
import json

import pytest

from core.payments.yookassa_webhook import (
    WebhookAuthError,
    canonical_webhook_event_payload,
    parse_notification,
    verify_webhook,
)
from runtime._internal.effects_clients import yookassa_webhook_server


@pytest.mark.parametrize(
    "configured_user,configured_password",
    [("", ""), ("merchant", ""), ("", "secret"), (None, None)],
)
def test_basic_verifier_rejects_unconfigured_credentials(
    configured_user, configured_password,
):
    supplied = f"{configured_user or ''}:{configured_password or ''}"
    header = base64.b64encode(supplied.encode()).decode()
    with pytest.raises(WebhookAuthError, match="missing_basic_credentials"):
        verify_webhook(
            headers={"Authorization": f"Basic {header}"},
            body_bytes=b"{}",
            auth_mode="basic",
            basic_user=configured_user,
            basic_pass=configured_password,
        )


@pytest.mark.parametrize("missing", ["YOOKASSA_WEBHOOK_BASIC_USER", "YOOKASSA_WEBHOOK_BASIC_PASS"])
def test_http_ingress_refuses_basic_mode_without_both_credentials(monkeypatch, missing):
    values = {
        "APP_ENV": "dev",
        "YOOKASSA_WEBHOOK_BASIC_USER": "merchant",
        "YOOKASSA_WEBHOOK_BASIC_PASS": "secret",
    }
    values[missing] = ""
    monkeypatch.setattr(
        yookassa_webhook_server,
        "env_str",
        lambda key, default="": values.get(key, default),
    )

    class Outbox:
        def enqueue_once(self, *, dedupe_key, payload):
            pytest.fail("unconfigured ingress must not enqueue a payment")

    with pytest.raises(RuntimeError, match="YOOKASSA_WEBHOOK_BASIC_CREDENTIALS_REQUIRED"):
        yookassa_webhook_server.start_yookassa_webhook_server_in_thread(
            host="127.0.0.1",
            port=0,
            path="/webhook",
            event_store=None,
            payment_outbox=Outbox(),
            auth_mode="basic",
        )


def test_audit_payload_does_not_persist_secret_or_unknown_yookassa_headers():
    body = json.dumps({
        "event": "payment.succeeded",
        "object": {"id": "payment-123"},
    }).encode()
    headers = {
        "Authorization": "Basic sensitive",
        "Cookie": "session=secret",
        "Set-Cookie": "token=secret",
        "X-YooKassa-Token": "secret-token",
        "X-YK-Signature": "secret-signature",
        "X-Y-Custom-Secret": "secret-value",
        "X-YooKassa-Request-Id": "provider-correlation",
        "X-Request-Id": "internal-correlation",
        "Content-Type": "application/json",
    }
    event, payload = canonical_webhook_event_payload(
        parse_notification(body_bytes=body), headers=headers, body_bytes=body,
    )
    assert event == "yookassa_webhook_received"
    assert payload["headers"] == {
        "X-YooKassa-Request-Id": "provider-correlation",
        "X-Request-Id": "internal-correlation",
        "Content-Type": "application/json",
    }
    assert "secret" not in repr(payload).lower()


def test_audit_header_values_remain_bounded():
    body = b'{"object":{"id":"payment-123"}}'
    _, payload = canonical_webhook_event_payload(
        parse_notification(body_bytes=body),
        headers={"X-Request-Id": "a" * 500},
        body_bytes=body,
    )
    assert payload["headers"] == {"X-Request-Id": "a" * 200}


def _header(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.mark.parametrize("user,password,accepted", [
    ("shop", "secret", True),
    ("wrong", "secret", False),
    ("shop", "wrong", False),
])
def test_core_verifier_compares_both_credentials(monkeypatch, user, password, accepted):
    original = hmac.compare_digest
    calls = []

    def observed(left, right):
        calls.append((left, right))
        return original(left, right)

    monkeypatch.setattr(hmac, "compare_digest", observed)
    kwargs = dict(headers=_header(user, password), body_bytes=b"{}", auth_mode="basic",
                  basic_user="shop", basic_pass="secret")
    if accepted:
        verify_webhook(**kwargs)
    else:
        with pytest.raises(WebhookAuthError, match="invalid_basic_credentials"):
            verify_webhook(**kwargs)
    assert calls == [(user, "shop"), (password, "secret")]


@pytest.mark.parametrize("user,password,expected_status,expected_compares", [
    ("shop", "secret", 200, 4),
    ("wrong", "secret", 401, 2),
    ("shop", "wrong", 401, 2),
])
def test_webhook_server_compares_both_credentials_before_enqueue(
    monkeypatch, user, password, expected_status, expected_compares,
):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("YOOKASSA_WEBHOOK_BASIC_USER", "shop")
    monkeypatch.setenv("YOOKASSA_WEBHOOK_BASIC_PASS", "secret")
    original = hmac.compare_digest
    calls = []

    def observed(left, right):
        calls.append((left, right))
        return original(left, right)

    monkeypatch.setattr(hmac, "compare_digest", observed)

    class Outbox:
        def __init__(self):
            self.jobs = []

        def enqueue_once(self, *, dedupe_key, payload):
            self.jobs.append((dedupe_key, payload))

    outbox = Outbox()
    server = yookassa_webhook_server.start_yookassa_webhook_server_in_thread(
        host="127.0.0.1", port=0, path="/yk", event_store=None,
        payment_outbox=outbox, auth_mode="basic",
    )
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
        try:
            connection.request("POST", "/yk", body=b'{"event":"payment.succeeded","object":{"id":"p1"}}',
                               headers=_header(user, password))
            response = connection.getresponse()
            assert response.status == expected_status
            response.read()
        finally:
            connection.close()
    finally:
        server.shutdown()
        server.server_close()
    assert len(calls) == expected_compares
    assert len(outbox.jobs) == (1 if expected_status == 200 else 0)


@pytest.mark.parametrize("auth_mode", ["none", "token", "basic"])
def test_forged_tenant_metadata_is_never_used_for_tenant_audit(monkeypatch, auth_mode):
    monkeypatch.setattr(yookassa_webhook_server, "env_str", lambda key, default="": {
        "APP_ENV": "dev",
        "YOOKASSA_WEBHOOK_IP_ALLOWLIST": "127.0.0.1/32",
        "YOOKASSA_WEBHOOK_BASIC_USER": "merchant",
        "YOOKASSA_WEBHOOK_BASIC_PASS": "secret",
    }.get(key, default))

    class Outbox:
        def __init__(self):
            self.jobs = []

        def enqueue_once(self, *, dedupe_key, payload):
            self.jobs.append((dedupe_key, payload))

    class TenantAudit:
        def __init__(self):
            self.events = []

        def emit(self, **event):
            self.events.append(event)

    outbox, audit = Outbox(), TenantAudit()
    server = yookassa_webhook_server.start_yookassa_webhook_server_in_thread(
        host="127.0.0.1", port=0, path="/webhook",
        event_store=audit, payment_outbox=outbox,
        auth_mode=auth_mode, webhook_token="test-token",
    )
    try:
        body = json.dumps({
            "event": "payment.succeeded",
            "tenant_id": "forged-top-level",
            "metadata": {"tenant_id": "forged-outer"},
            "object": {"id": "payment-42", "status": "succeeded",
                       "metadata": {"tenant_id": "victim-tenant", "tenant": "another"}},
        }).encode()
        headers = {"Content-Type": "application/json"}
        if auth_mode == "token":
            headers["X-Webhook-Token"] = "test-token"
        elif auth_mode == "basic":
            credentials = base64.b64encode(b"merchant:secret").decode()
            headers["Authorization"] = f"Basic {credentials}"
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        try:
            conn.request("POST", "/webhook", body=body, headers=headers)
            response = conn.getresponse()
            assert response.status == 200
            response.read()
        finally:
            conn.close()
        assert len(outbox.jobs) == 1
        assert outbox.jobs[0][1]["payload"]["object"]["id"] == "payment-42"
        assert audit.events == []
    finally:
        server.shutdown()
        server.server_close()
