"""A malformed or oversized YooKassa request must never occupy the outbox."""

from __future__ import annotations

import http.client
import json

import pytest

from runtime._internal.effects_clients import yookassa_webhook_server as webhook


@pytest.mark.parametrize(
    "declared_length, expected_status",
    [("1048577", 413), ("999999999999999", 413), ("0", 400), ("-1", 400), ("invalid", 400)],
)
def test_webhook_rejects_unbounded_or_invalid_content_length_before_read(
    monkeypatch, declared_length, expected_status,
):
    monkeypatch.setattr(
        webhook, "env_str", lambda name, default="": {"APP_ENV": "dev"}.get(name, default)
    )

    class Outbox:
        def __init__(self):
            self.jobs = []

        def enqueue_once(self, *, dedupe_key, payload):
            self.jobs.append((dedupe_key, payload))

    outbox = Outbox()
    server = webhook.start_yookassa_webhook_server_in_thread(
        host="127.0.0.1", port=0, path="/webhook",
        event_store=None, payment_outbox=outbox, auth_mode="none",
    )
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        try:
            conn.putrequest("POST", "/webhook")
            conn.putheader("Content-Length", declared_length)
            conn.endheaders()  # Deliberately send no body; server must not wait for it.
            response = conn.getresponse()
            assert response.status == expected_status
            response.read()
        finally:
            conn.close()
        assert outbox.jobs == []

        # Rejected input cannot poison the listener or prevent the next real
        # notification from reaching the canonical durable outbox.
        valid = json.dumps({
            "event": "payment.succeeded", "object": {"id": "payment-bounded"}
        }).encode()
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        try:
            conn.request("POST", "/webhook", body=valid)
            response = conn.getresponse()
            assert response.status == 200
            response.read()
        finally:
            conn.close()
        assert len(outbox.jobs) == 1
        assert outbox.jobs[0][0].endswith("payment.succeeded:payment-bounded")
    finally:
        server.shutdown()
        server.server_close()
