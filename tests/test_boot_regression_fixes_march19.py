from __future__ import annotations


def test_env_guard_accepts_mode_alias_and_production_name(monkeypatch):
    from runtime.boot.env import env_guard_production_mode

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("RUN_MODE", raising=False)
    monkeypatch.setenv("MODE", "tg")
    monkeypatch.setenv("BOT_TOKEN", "12345678")
    env_guard_production_mode()


class _ScopedTenant:
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id


class _ScopedEventLog:
    def __init__(self, tenant_id: str) -> None:
        self._tenant = _ScopedTenant(tenant_id)
        self.events: list[dict] = []

    def emit(self, **kwargs):
        self.events.append(kwargs)
        return kwargs


def test_emit_system_event_supports_tenant_scoped_event_log():
    from runtime.boot.boot_helpers import _emit_system_event

    event_log = _ScopedEventLog("tenant-1")
    _emit_system_event(event_log, "boot_event", {"ok": True})

    assert event_log.events
    assert event_log.events[0]["event_type"] == "boot_event"
    assert "tenant_id" not in event_log.events[0]


class _StrictStore:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_event(self, *, tenant_id: str, event_type: str, user_id: str, payload: dict, ts=None):
        if not str(tenant_id or "").strip():
            raise ValueError("tenant_id required")
        self.events.append({"tenant_id": tenant_id, "event_type": event_type, "payload": payload})

    def iter_events(self, *, tenant_id: str, user_id: str, since_ts: int, limit: int = 100):
        if not str(tenant_id or "").strip():
            raise ValueError("tenant_id required")
        return []

    def count_events(self, *, tenant_id: str, user_id: str, since_ts: int):
        if not str(tenant_id or "").strip():
            raise ValueError("tenant_id required")
        return len(self.events)


class _ScopedStrictEventLog:
    def __init__(self, store: _StrictStore, tenant_id: str) -> None:
        self._tenant = _ScopedTenant(tenant_id)
        self._store = store

    def emit(self, *, event_type: str, user_id: str, payload: dict, source: str = "system"):
        tenant_id = self._tenant.tenant_id
        if not str(tenant_id or "").strip():
            raise ValueError("tenant_id required")
        self._store.append_event(tenant_id=tenant_id, event_type=event_type, user_id=user_id, payload=payload)


def test_tenant_hard_gate_accepts_tenant_scoped_event_log():
    from runtime.boot.tenant_hard_gate import validate_runtime_objects

    store = _StrictStore()
    event_log = _ScopedStrictEventLog(store, "tenant-1")
    validate_runtime_objects(tenant_id="tenant-1", event_store=store, event_log=event_log)


def test_runtime_bootstrap_is_idempotent(monkeypatch):
    import runtime.bootstrap as bootstrap_mod

    monkeypatch.setattr(bootstrap_mod, "apply_process_hygiene", lambda: None)
    monkeypatch.setattr(bootstrap_mod, "setup_logging", lambda: None)
    monkeypatch.setattr(bootstrap_mod, "activate_import_firewall", lambda: None)
    monkeypatch.setattr(bootstrap_mod, "verify_release_attestation_if_needed", lambda: None)
    monkeypatch.setattr(bootstrap_mod, "enforce_production_strict_mode", lambda: None)
    monkeypatch.setattr(bootstrap_mod, "enforce_two_admins_in_prod_or_explain", lambda: None)
    monkeypatch.setattr(bootstrap_mod, "maybe_disable_singleton_lock_in_dev_test", lambda: None)

    calls = {"acquire": 0, "release": 0}

    class DummyLock:
        def acquire(self):
            calls["acquire"] += 1

        def release(self):
            calls["release"] += 1

    monkeypatch.setattr(bootstrap_mod, "SingletonLock", DummyLock)
    monkeypatch.setattr(bootstrap_mod, "_BOOTSTRAP_DONE", False)
    monkeypatch.setattr(bootstrap_mod, "_SINGLETON_LOCK", None)

    bootstrap_mod.bootstrap()
    bootstrap_mod.bootstrap()

    assert calls["acquire"] == 1
    bootstrap_mod._release_singleton_lock()
    assert calls["release"] == 1
