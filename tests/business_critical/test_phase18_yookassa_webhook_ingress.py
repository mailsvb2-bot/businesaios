"""Webhook ingress cannot acknowledge an unpersisted payment or a replay-unsafe queue."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime._internal.effects_clients import yookassa_webhook_server as webhook


class DurableOutbox:
    def __init__(self):
        self.keys = set()

    def enqueue_once(self, *, dedupe_key, payload):
        self.keys.add(dedupe_key)


def _start(monkeypatch, *, outbox, auth="token", production=False, allowlist=""):
    monkeypatch.setattr(webhook, "env_str", lambda key, default="": {
        "APP_ENV": "production" if production else "dev",
        "YOOKASSA_WEBHOOK_AUTH_MODE": auth,
        "YOOKASSA_WEBHOOK_IP_ALLOWLIST": allowlist,
    }.get(key, default))
    # Never reach actual listener for these preflight failures.
    monkeypatch.setattr(webhook, "HTTPServer", lambda *args: pytest.fail("server started"))
    return webhook.start_yookassa_webhook_server_in_thread(
        host="127.0.0.1", port=12345, path="/webhook",
        event_store=None, payment_outbox=outbox, auth_mode=auth,
    )


@pytest.mark.parametrize("outbox", [None, object(), SimpleNamespace(enqueue=lambda p: None)])
def test_no_durable_idempotent_queue_refuses_startup(monkeypatch, outbox):
    with pytest.raises(RuntimeError, match="DURABLE_IDEMPOTENT_OUTBOX_REQUIRED"):
        _start(monkeypatch, outbox=outbox)


@pytest.mark.parametrize("auth", ["invalid", "disabled", "unknown"])
def test_unknown_auth_scheme_refuses_startup(monkeypatch, auth):
    with pytest.raises(RuntimeError, match="AUTH_MODE unsupported"):
        _start(monkeypatch, outbox=DurableOutbox(), auth=auth)


def test_production_without_trusted_ip_allowlist_refuses_startup(monkeypatch):
    with pytest.raises(RuntimeError, match="IP_ALLOWLIST required"):
        _start(monkeypatch, outbox=DurableOutbox(), production=True)


def test_refund_job_uses_original_payment_id_and_preserves_refund_identity():
    from interfaces.telegram.runtime_loops.payment_jobs import _normalize_webhook_job

    job = _normalize_webhook_job({
        "type": "yookassa_webhook",
        "payload": {
            "event": "refund.succeeded",
            "object": {
                "id": "refund-1", "payment_id": "payment-1",
                "status": "succeeded",
            },
        },
    })
    assert job["external_id"] == "payment-1"
    assert job["refund_id"] == "refund-1"
    assert job["event"] == "refund.succeeded"


@pytest.mark.parametrize("object_", [
    {"id": "refund-1"},
    {"id": "refund-1", "payment_id": ""},
    {"payment_id": "payment-1"},
])
def test_refund_missing_provider_identity_is_never_normalized(object_):
    from interfaces.telegram.runtime_loops.payment_jobs import _normalize_webhook_job

    with pytest.raises(ValueError):
        _normalize_webhook_job({
            "type": "yookassa_webhook",
            "payload": {"event": "refund.succeeded", "object": object_},
        })
