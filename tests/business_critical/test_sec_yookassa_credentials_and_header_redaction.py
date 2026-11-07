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


def test_basic_auth_evaluates_password_even_when_username_is_wrong(monkeypatch):
    from core.payments import yookassa_webhook

    calls = []
    real_compare = yookassa_webhook.hmac.compare_digest

    def observed_compare(actual, expected):
        calls.append((actual, expected))
        return real_compare(actual, expected)

    monkeypatch.setattr(yookassa_webhook.hmac, "compare_digest", observed_compare)
    token = base64.b64encode(b"wrong-user:wrong-pass").decode()
    with pytest.raises(WebhookAuthError, match="invalid_basic_credentials"):
        verify_webhook(
            headers={"Authorization": f"Basic {token}"},
            body_bytes=b"{}",
            auth_mode="basic",
            basic_user="merchant",
            basic_pass="secret",
        )
    assert calls == [("wrong-user", "merchant"), ("wrong-pass", "secret")]
