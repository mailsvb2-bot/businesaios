from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _OutboxStub:
    items: list[dict[str, Any]] = field(default_factory=list)

    def enqueue_once(self, *, dedupe_key: str, payload: dict[str, Any]) -> None:
        # Best-effort idempotency for the test.
        for it in self.items:
            if it.get("dedupe_key") == dedupe_key:
                return
        self.items.append({"dedupe_key": dedupe_key, "payload": payload})

def test_yookassa_webhook_server_accepts_post_and_enqueues_outbox(monkeypatch, unused_tcp_port):
    # Configure token auth (recommended)
    monkeypatch.setenv("YOOKASSA_WEBHOOK_AUTH_MODE", "token")
    monkeypatch.setenv("YOOKASSA_WEBHOOK_TOKEN", "test-token-123")

    port = int(unused_tcp_port)
    outbox = _OutboxStub()

    from runtime.effects import start_yookassa_webhook_server_in_thread

    # event_store is optional for this smoke test
    start_yookassa_webhook_server_in_thread(
        host="127.0.0.1",
        port=port,
        path="/yookassa/webhook",
        event_store=None,
        payment_outbox=outbox,
    )

    # POST a minimal notification
    body = {
        "event": "payment.succeeded",
        "object": {"id": "pay_test_1", "type": "payment"},
    }

    import http.client

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    conn.request(
        "POST",
        "/yookassa/webhook",
        body=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Token": "test-token-123",
        },
    )
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", errors="ignore")
    conn.close()

    assert resp.status == 200, data

    # Give the handler a moment to enqueue (threaded server)
    deadline = time.time() + 2.0
    while time.time() < deadline and not outbox.items:
        time.sleep(0.02)

    assert outbox.items, "webhook server did not enqueue any outbox job"
    payload = outbox.items[0]["payload"]
    assert payload.get("type") == "yookassa_webhook"
    # This server enqueues the raw notification inside payload["payload"]
    raw = payload.get("payload") or {}
    assert isinstance(raw, dict)
    obj = raw.get("object") or {}
    assert isinstance(obj, dict)
    assert str(obj.get("id") or "") == "pay_test_1"
    assert str(raw.get("event") or "") == "payment.succeeded"
