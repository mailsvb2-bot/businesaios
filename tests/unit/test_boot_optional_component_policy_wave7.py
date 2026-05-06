from __future__ import annotations

from contextlib import ExitStack

import pytest

from runtime.boot import phase_policy_registry, phase_retention


class _Preg:
    def activate_bootstrap(self, policy_id: str) -> None:
        raise LookupError(policy_id)


class _Core:
    env = "prod"
    production_strict_mode = True


class _Settings:
    core = _Core()
    guard = type("Guard", (), {"admin_user_ids": ""})()


class _Queue:
    def metrics_snapshot(self):
        return {"qsize": 1, "by_priority": {"best_effort": {"wait_ms": {"p95": 12}}}}


class _Store:
    def close(self) -> None:
        return None


def test_bootstrap_policy_activation_is_fail_closed_in_strict_mode(monkeypatch) -> None:
    monkeypatch.setattr(phase_policy_registry, "env_str", lambda *_args, **_kwargs: "missing")
    with pytest.raises(RuntimeError, match="BOOT_COMPONENT_FAILED:bootstrap_policy_activation"):
        phase_policy_registry._activate_bootstrap_policy(preg=_Preg(), settings=_Settings())


def test_retention_cooldown_store_uses_optional_component_policy(monkeypatch) -> None:
    monkeypatch.setattr(phase_retention, "resolve_optional_boot_component", lambda **kwargs: kwargs["builder"]())
    monkeypatch.setattr(
        "observability.platform.snapshot_store.offer_cooldowns_sqlite.OfferCooldownStoreSqlite",
        lambda path: type("Factory", (), {"open": lambda self: _Store()})(),
    )
    with ExitStack() as stack:
        store = phase_retention._open_cooldown_store(base="/tmp", stack=stack)
    assert isinstance(store, _Store)
