"""Independent regressions for constant-time YooKassa Basic authentication."""

import base64
import hmac
import http.client

import pytest

from core.payments.yookassa_webhook import WebhookAuthError, verify_webhook
from runtime._internal.effects_clients import yookassa_webhook_server


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
