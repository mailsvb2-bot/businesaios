from __future__ import annotations

from pathlib import Path

import pytest

from runtime.boot.tenant_hard_gate import validate_runtime_objects


class _TenantLog:
    tenant_id = "default"

    def emit(self, *, event_type: str, user_id: str, payload: dict):
        return {"event_type": event_type, "user_id": user_id, "payload": payload}


class _IterableStore:
    def iter_events(self, *, tenant_id: str, user_id: str, since_ts: int, limit: int = 100):
        return []


def _validate(store, log=None) -> None:
    validate_runtime_objects(
        tenant_id="default",
        event_store=store,
        event_log=log or _TenantLog(),
    )


def test_tenant_hard_gate_rejects_empty_tenant_on_store_and_log():
    class Store(_IterableStore):
        def append_event(self, *, tenant_id: str, event_type: str, user_id: str, payload: dict, ts=None):
            if not str(tenant_id or "").strip():
                raise ValueError("tenant_id required")

        def count_events(self, *, tenant_id: str, user_id: str, since_ts: int):
            if not str(tenant_id or "").strip():
                raise ValueError("tenant_id required")
            return 0

    class Log:
        def __init__(self, store):
            self.store = store

        def emit(self, *, tenant_id: str, event_type: str, user_id: str, payload: dict):
            if not str(tenant_id or "").strip():
                raise ValueError("tenant_id required")
            if tenant_id == "__other__":
                raise ValueError("cross-tenant forbidden")
            self.store.append_event(
                tenant_id=tenant_id,
                event_type=event_type,
                user_id=user_id,
                payload=payload,
            )

    store = Store()
    _validate(store, Log(store))


def test_tenant_hard_gate_fails_if_store_missing_tenant_param():
    class BadStore:
        def append_event(self, *, event_type: str, user_id: str, payload: dict, ts=None):
            return None

        def iter_events(self, *, user_id: str, since_ts: int, limit: int = 100):
            return []

    with pytest.raises(SystemExit):
        _validate(BadStore())


def test_tenant_hard_gate_accepts_strict_event_payload_store():
    class PayloadStore(_IterableStore):
        def append_event(self, event: dict):
            if not str(event.get("tenant_id") or "").strip():
                raise ValueError("tenant_id required")

    _validate(PayloadStore())


@pytest.mark.parametrize("append_event", [
    lambda self, *, event: (_ for _ in ()).throw(ValueError("tenant_id required")),
    lambda self, event, required: (_ for _ in ()).throw(ValueError("tenant_id required")),
])
def test_tenant_hard_gate_rejects_unusable_event_call_shapes(append_event):
    store_type = type("UnusableStore", (_IterableStore,), {"append_event": append_event})
    with pytest.raises(SystemExit):
        _validate(store_type())


def test_tenant_hard_gate_rejects_type_error_from_event_payload_store():
    class BrokenPayloadStore(_IterableStore):
        def append_event(self, event: dict):
            raise TypeError("internal payload handling failed")

    with pytest.raises(SystemExit, match="contract is unusable"):
        _validate(BrokenPayloadStore())


def test_tenant_hard_gate_audits_repository_root(monkeypatch: pytest.MonkeyPatch):
    import bootstrap.tenant_hard_gate as gate

    seen: list[str] = []
    monkeypatch.setattr("scripts.audit_tenant_usage.audit", lambda root: seen.append(root) or 0)
    gate.preflight_env(
        run_mode="telegram",
        cfg=gate.TenantHardGateConfig(audit_repo=True, require_env_tenant=False),
    )
    assert seen == [str(Path(gate.__file__).resolve().parents[1])]
