"""YooKassa ingress cannot invent a tenant from unsigned payment metadata."""

from __future__ import annotations

import base64
import http.client
import json

import pytest

from runtime._internal.effects_clients import yookassa_webhook_server as webhook


@pytest.mark.parametrize("auth_mode", ["none", "token", "basic"])
def test_forged_tenant_metadata_is_never_used_for_tenant_audit(monkeypatch, auth_mode):
    monkeypatch.setattr(webhook, "env_str", lambda key, default="": {
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
    server = webhook.start_yookassa_webhook_server_in_thread(
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
