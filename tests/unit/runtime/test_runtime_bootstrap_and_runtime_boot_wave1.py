from __future__ import annotations

from types import SimpleNamespace

import runtime.bootstrap as runtime_bootstrap
import runtime.runtime_boot as runtime_runtime_boot
from runtime.runtime_boot import boot_runtime


class _DummyLock:
    def __init__(self) -> None:
        self.acquired = False
        self.released = False

    def acquire(self) -> None:
        self.acquired = True

    def release(self) -> None:
        self.released = True


class _FakeRuntime:
    def __init__(self) -> None:
        self.artifacts = SimpleNamespace(registry={"ok": True})


def test_bootstrap_runs_guards_every_call_but_hygiene_once(monkeypatch) -> None:
    calls: list[str] = []
    lock = _DummyLock()

    monkeypatch.setattr(runtime_bootstrap, "_BOOTSTRAP_DONE", False)
    monkeypatch.setattr(runtime_bootstrap, "_SINGLETON_LOCK", None)
    monkeypatch.setattr(runtime_bootstrap, "verify_release_attestation_if_needed", lambda: calls.append("attestation"))
    monkeypatch.setattr(runtime_bootstrap, "enforce_production_strict_mode", lambda: calls.append("strict"))
    monkeypatch.setattr(runtime_bootstrap, "enforce_two_admins_in_prod_or_explain", lambda: calls.append("admins"))
    monkeypatch.setattr(runtime_bootstrap, "maybe_disable_singleton_lock_in_dev_test", lambda: calls.append("devtest"))
    monkeypatch.setattr(runtime_bootstrap, "apply_process_hygiene", lambda: calls.append("hygiene"))
    monkeypatch.setattr(runtime_bootstrap, "setup_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(runtime_bootstrap, "activate_import_firewall", lambda: calls.append("firewall"))
    monkeypatch.setattr(runtime_bootstrap, "SingletonLock", lambda: lock)
    monkeypatch.setattr(runtime_bootstrap.atexit, "register", lambda fn: calls.append("atexit"))

    runtime_bootstrap.bootstrap(acquire_singleton_lock=True)
    runtime_bootstrap.bootstrap(acquire_singleton_lock=True)

    assert calls.count("attestation") == 2
    assert calls.count("strict") == 2
    assert calls.count("admins") == 2
    assert calls.count("devtest") == 2
    assert calls.count("hygiene") == 1
    assert calls.count("logging") == 1
    assert calls.count("firewall") == 1
    assert lock.acquired is True


def test_runtime_boot_delegates_to_sovereign_bootstrap_owner(monkeypatch) -> None:
    fake_runtime = _FakeRuntime()
    monkeypatch.setattr(runtime_runtime_boot, "_load_sovereign_bootstrap_runtime", lambda: (lambda project_root=None: fake_runtime))

    registry = boot_runtime()

    assert registry == {"ok": True}
