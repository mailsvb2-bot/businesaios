from __future__ import annotations

import pytest


def test_tenant_hard_gate_rejects_empty_tenant_on_store_and_log():
    from runtime.boot.tenant_hard_gate import validate_runtime_objects

    class DummyStore:
        def append_event(self, *, tenant_id: str, event_type: str, user_id: str, payload: dict, ts=None):
            if not str(tenant_id or "").strip():
                raise ValueError("tenant_id required")
            return None

        def iter_events(self, *, tenant_id: str, user_id: str, since_ts: int, limit: int = 100):
            if not str(tenant_id or "").strip():
                raise ValueError("tenant_id required")
            return []

        def count_events(self, *, tenant_id: str, user_id: str, since_ts: int):
            if not str(tenant_id or "").strip():
                raise ValueError("tenant_id required")
            return 0

    class DummyLog:
        def __init__(self, store):
            self.store = store

        def emit(self, *, tenant_id: str, event_type: str, user_id: str, payload: dict):
            if not str(tenant_id or "").strip():
                raise ValueError("tenant_id required")
            if tenant_id == "__other__":
                raise ValueError("cross-tenant forbidden")
            self.store.append_event(tenant_id=tenant_id, event_type=event_type, user_id=user_id, payload=payload)

    store = DummyStore()
    elog = DummyLog(store)

    # Must not raise for a valid tenant_id.
    validate_runtime_objects(tenant_id="default", event_store=store, event_log=elog)


def test_tenant_hard_gate_fails_if_store_missing_tenant_param():
    from runtime.boot.tenant_hard_gate import validate_runtime_objects

    class BadStore:
        # tenant_id missing on purpose
        def append_event(self, *, event_type: str, user_id: str, payload: dict, ts=None):
            return None

        def iter_events(self, *, user_id: str, since_ts: int, limit: int = 100):
            return []

    class BadLog:
        def emit(self, *, tenant_id: str, event_type: str, user_id: str, payload: dict):
            return None

    with pytest.raises(SystemExit):
        validate_runtime_objects(tenant_id="default", event_store=BadStore(), event_log=BadLog())
