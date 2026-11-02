"""Independent regressions for YooKassa credential configuration and audit redaction."""

from __future__ import annotations

import base64
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
