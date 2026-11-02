"""Adversarial regressions for the canonical YooKassa webhook verifier.

These tests deliberately exercise pure production owners, without replacing the
runtime payment ingress or introducing an alternative payment execution path.
"""
from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from core.payments.yookassa_webhook import (
    WebhookAuthError,
    canonical_webhook_event_payload,
    parse_notification,
    redact_headers,
    verify_webhook,
)


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
