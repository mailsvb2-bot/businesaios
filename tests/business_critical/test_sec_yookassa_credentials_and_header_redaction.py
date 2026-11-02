"""Independent regressions for YooKassa auth, audit redaction and tenant isolation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import json

import pytest

from core.payments.yookassa_webhook import (
    WebhookAuthError,
    canonical_webhook_event_payload,
    parse_notification,
    redact_headers,
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


def _basic(user: str, password: str) -> dict[str, str]:
    encoded = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


@pytest.mark.parametrize("user,password", [
    (None, None), ("", ""), (None, "secret"), ("login", None),
    ("", "secret"), ("login", ""),
])
def test_basic_auth_fails_closed_if_any_configured_credential_missing(user, password):
    with pytest.raises(WebhookAuthError, match="missing_basic_credentials"):
        verify_webhook(
            headers=_basic("login", "secret"), body_bytes=b"{}",
            auth_mode="basic", basic_user=user, basic_pass=password,
        )


@pytest.mark.parametrize("provided", [
    {}, {"Authorization": "Bearer token"},
    _basic("wrong", "secret"), _basic("login", "wrong"),
    {"Authorization": "Basic not-base64"},
])
def test_basic_auth_rejects_missing_malformed_or_wrong_credentials(provided):
    with pytest.raises(WebhookAuthError):
        verify_webhook(
            headers=provided, body_bytes=b"{}",
            auth_mode="basic", basic_user="login", basic_pass="secret",
        )


def test_basic_auth_accepts_exact_credentials():
    verify_webhook(
        headers=_basic("login", "secret"), body_bytes=b"{}",
        auth_mode="basic", basic_user="login", basic_pass="secret",
    )


def test_hmac_signature_binds_exact_body_and_secret():
    body = b'{"object":{"id":"p1"},"event":"payment.succeeded"}'
    signature = hmac.new(b"key", body, hashlib.sha256).hexdigest()
    verify_webhook(
        headers={"X-YK-Signature": signature}, body_bytes=body,
        auth_mode="hmac_sha256", hmac_secret="key",
    )
    for changed_body, changed_key, changed_sig in [
        (body + b" ", "key", signature),
        (body, "other", signature),
        (body, "key", "0" * 64),
    ]:
        with pytest.raises(WebhookAuthError, match="bad_signature"):
            verify_webhook(
                headers={"X-YK-Signature": changed_sig},
                body_bytes=changed_body,
                auth_mode="hmac_sha256", hmac_secret=changed_key,
            )


def test_webhook_audit_drops_tokens_cookies_signatures_and_unrecognized_headers():
    incoming = {
        "Authorization": "Bearer private",
        "Cookie": "sid=private",
        "X-YK-Signature": "private",
        "X-YooKassa-Token": "private",
        "X-Unknown-Secret": "private",
        "X-Request-Id": "r-123",
        "User-Agent": "unit-test",
    }
    result = redact_headers(incoming)
    assert result == {"X-Request-Id": "r-123", "User-Agent": "unit-test"}
    assert "private" not in repr(result)


def test_webhook_audit_caps_correlation_header_and_does_not_copy_payload_metadata():
    body = (
        b'{"event":"payment.succeeded","object":{"id":"payment-1",'
        b'"metadata":{"tenant_id":"forged-tenant","api_key":"private"}}}'
    )
    parsed = parse_notification(body_bytes=body)
    kind, audit = canonical_webhook_event_payload(
        parsed, headers={"X-Request-Id": "x" * 400, "Authorization": "private"},
        body_bytes=body,
    )
    assert kind == "yookassa_webhook_received"
    assert audit["external_id"] == "payment-1"
    assert audit["headers"] == {"X-Request-Id": "x" * 200}
    assert "forged-tenant" not in repr(audit)
    assert "private" not in repr(audit)
