"""Real HTTP ingress: durable queue first, never a fabricated receipt."""
from __future__ import annotations

import http.client
import json

import pytest

from runtime._internal.effects_actions.payments.yookassa import yookassa_create_payment
from runtime._internal.effects_clients import yookassa_webhook_server as webhook


class Outbox:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.jobs = {}

    def enqueue_once(self, *, dedupe_key, payload):
        if self.fail:
            raise OSError("durable store unavailable")
        self.jobs.setdefault(dedupe_key, payload)


class Audit:
    def __init__(self):
        self.events = []

    def emit(self, **kwargs):
        self.events.append(kwargs)


def _post(port):
    body = json.dumps({
        "event": "payment.succeeded", "object": {
            "id": "payment-1", "status": "succeeded",
        },
    }).encode()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("POST", "/webhook", body, {
            "Content-Type": "application/json",
            "X-Webhook-Token": "local-secret",
        })
        return conn.getresponse().status
    finally:
        conn.close()


def test_http_webhook_ack_requires_durable_enqueue(monkeypatch):
    monkeypatch.setattr(webhook, "env_str", lambda key, default="": {
        "APP_ENV": "dev", "YOOKASSA_WEBHOOK_IP_ALLOWLIST": "127.0.0.1/32",
    }.get(key, default))
    for failed in (True, False):
        outbox, audit = Outbox(fail=failed), Audit()
        server = webhook.start_yookassa_webhook_server_in_thread(
            host="127.0.0.1", port=0, path="/webhook",
            event_store=audit, payment_outbox=outbox,
            auth_mode="token", webhook_token="local-secret",
        )
        try:
            assert _post(server.server_port) == (503 if failed else 200)
            assert len(outbox.jobs) == (0 if failed else 1)
            assert audit.events == []  # Untrusted ingress cannot author tenant audit.
            if not failed:
                assert _post(server.server_port) == 200
                assert len(outbox.jobs) == 1
        finally:
            server.shutdown()
            server.server_close()

@pytest.mark.parametrize("currency,amount", [
    ("RUB", 100), ("USD", 100), ("RUB", 0),
])
def test_payment_create_is_rejected_before_any_psp_side_effect(currency, amount):
    class NoCalls:
        def __getattr__(self, attr):
            raise AssertionError("External transport unexpectedly touched: " + attr)

    with pytest.raises(RuntimeError, match="SIDE_EFFECT_REQUIRES_EXECUTOR"):
        yookassa_create_payment(
            effects=NoCalls(), decision_id="decision-1", amount=amount,
            currency=currency, user_id="user-1",
            metadata={"order_id": "order-1"},
        )
