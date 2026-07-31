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


def test_tenant_hard_gate_accepts_strict_event_payload_store():
    from runtime.boot.tenant_hard_gate import validate_runtime_objects

    class PayloadStore:
        def append_event(self, event: dict):
            if not str(event.get("tenant_id") or "").strip():
                raise ValueError("tenant_id required")
            return None

        def iter_events(self, *, tenant_id: str, user_id: str, since_ts: int, limit: int = 100):
            if not str(tenant_id or "").strip():
                raise ValueError("tenant_id required")
            return []

    class TenantLog:
        tenant_id = "default"

        def emit(self, *, event_type: str, user_id: str, payload: dict):
            return {"event_type": event_type, "user_id": user_id, "payload": payload}

    validate_runtime_objects(tenant_id="default", event_store=PayloadStore(), event_log=TenantLog())


def test_tenant_hard_gate_rejects_keyword_only_event_payload_store():
    from runtime.boot.tenant_hard_gate import validate_runtime_objects

    class KeywordOnlyStore:
        def append_event(self, *, event: dict):
            raise ValueError("tenant_id required")

        def iter_events(self, *, tenant_id: str, user_id: str, since_ts: int, limit: int = 100):
            return []

    class TenantLog:
        tenant_id = "default"

        def emit(self, *, event_type: str, user_id: str, payload: dict):
            return None

    with pytest.raises(SystemExit):
        validate_runtime_objects(
            tenant_id="default",
            event_store=KeywordOnlyStore(),
            event_log=TenantLog(),
        )


def test_tenant_hard_gate_rejects_event_store_with_extra_required_argument():
    from runtime.boot.tenant_hard_gate import validate_runtime_objects

    class ExtraArgumentStore:
        def append_event(self, event: dict, required: object):
            raise ValueError("tenant_id required")

        def iter_events(self, *, tenant_id: str, user_id: str, since_ts: int, limit: int = 100):
            return []

    class TenantLog:
        tenant_id = "default"

        def emit(self, *, event_type: str, user_id: str, payload: dict):
            return None

    with pytest.raises(SystemExit):
        validate_runtime_objects(
            tenant_id="default",
            event_store=ExtraArgumentStore(),
            event_log=TenantLog(),
        )


def test_tenant_hard_gate_rejects_type_error_from_event_payload_store():
    from runtime.boot.tenant_hard_gate import validate_runtime_objects

    class BrokenPayloadStore:
        def append_event(self, event: dict):
            raise TypeError("internal payload handling failed")

        def iter_events(self, *, tenant_id: str, user_id: str, since_ts: int, limit: int = 100):
            return []

    class TenantLog:
        tenant_id = "default"

        def emit(self, *, event_type: str, user_id: str, payload: dict):
            return None

    with pytest.raises(SystemExit, match="contract is unusable"):
        validate_runtime_objects(
            tenant_id="default",
            event_store=BrokenPayloadStore(),
            event_log=TenantLog(),
        )


def test_tenant_hard_gate_audits_repository_root(monkeypatch: pytest.MonkeyPatch):
    from pathlib import Path

    import bootstrap.tenant_hard_gate as gate

    seen: list[str] = []
    monkeypatch.setattr("scripts.audit_tenant_usage.audit", lambda root: seen.append(root) or 0)
    gate.preflight_env(run_mode="telegram", cfg=gate.TenantHardGateConfig(audit_repo=True, require_env_tenant=False))

    assert seen == [str(Path(gate.__file__).resolve().parents[1])]
