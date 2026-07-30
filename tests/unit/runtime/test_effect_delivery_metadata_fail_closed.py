from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.execution.executor_effect_delivery import attach_effect_delivery_metadata


def _env():
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            payload={"tenant_id": "tenant-1"},
        )
    )


def test_effect_delivery_metadata_propagates_outbox_read_failure(monkeypatch):
    executor = SimpleNamespace(_outbox=object(), _reliability=None)

    def fail_get_delivery_info(*args, **kwargs):
        raise RuntimeError("OUTBOX_READ_FAILED")

    monkeypatch.setattr(
        "runtime.execution.executor_effect_delivery.get_delivery_info",
        fail_get_delivery_info,
    )

    with pytest.raises(RuntimeError, match="OUTBOX_READ_FAILED"):
        attach_effect_delivery_metadata(executor, env=_env(), output={"ok": True})


def test_effect_delivery_metadata_propagates_reconciliation_failure():
    reliability = SimpleNamespace(
        reconcile=lambda env: (_ for _ in ()).throw(RuntimeError("RECONCILIATION_FAILED"))
    )
    executor = SimpleNamespace(_outbox=None, _reliability=reliability)

    with pytest.raises(RuntimeError, match="RECONCILIATION_FAILED"):
        attach_effect_delivery_metadata(executor, env=_env(), output={"ok": True})


def test_effect_delivery_metadata_keeps_verified_delivery_fields(monkeypatch):
    executor = SimpleNamespace(
        _outbox=object(),
        _reliability=SimpleNamespace(reconcile=lambda env: {"state": "completed"}),
    )

    monkeypatch.setattr(
        "runtime.execution.executor_effect_delivery.get_delivery_info",
        lambda *args, **kwargs: {
            "status": "delivered",
            "retry_count": 0,
            "backend_name": "sqlite",
            "external_id": "external-1",
            "effect_key": "effect-1",
            "effect_kind": "message",
            "payload_digest": "digest-1",
            "delivered_at": "2026-07-30T10:00:00Z",
            "delivery_metadata": {"provider": "test"},
        },
    )

    result = attach_effect_delivery_metadata(executor, env=_env(), output={"ok": True})

    assert result["ok"] is True
    assert result["effect_delivery"]["runtime_outbox_status"] == "delivered"
    assert result["effect_delivery"]["reconciliation"] == {"state": "completed"}
