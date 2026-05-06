from __future__ import annotations

import pytest

from runtime.boot.actions_registry import SPECS, INLINE_ALLOWLIST, all_actions
from runtime.boot.registration_manifest import registered_action_names



@pytest.mark.lock
def test_actions_registry_matches_boot_registration_manifest():
    expected = all_actions()
    registered = set(registered_action_names())
    assert registered == expected, f"registry drift: missing={sorted(expected-registered)} extra={sorted(registered-expected)}"


@pytest.mark.lock
def test_no_unregistered_handlers_register_calls_anywhere():
    """Forbid introducing a new runtime-action without updating the canonical registry."""
    expected = all_actions()
    offenders: list[str] = []
    from pathlib import Path
    import re
    for p in Path("runtime").rglob("*.py"):
        txt = p.read_text(encoding="utf-8")
        for a in re.findall(r'handlers\.register\(\s*"([^"]+)"', txt):
            if a not in expected:
                offenders.append(f"{p}:{a}")
    assert not offenders, "unregistered runtime-actions found:\n" + "\n".join(sorted(offenders))


@pytest.mark.lock
def test_every_action_has_limits_and_handler_contract():
    for name, spec in SPECS.items():
        assert spec.name == name
        assert spec.limits is not None
        if name == "noop@v1":
            assert spec.limits.kind == "none"
        else:
            assert spec.limits.kind != "none"
            assert spec.limits.per_tenant_per_min > 0
            assert spec.limits.per_user_per_min > 0

        assert spec.handler_ref and isinstance(spec.handler_ref, str)

        if name not in INLINE_ALLOWLIST:
            assert spec.handler_ref.startswith(("runtime.handlers.", "runtime.handlers_")), spec.handler_ref


@pytest.mark.lock
def test_idempotency_requirement_is_explicit_and_consistent():
    read_only = {"noop@v1", "poll_telegram_updates@v1", "telegram_self_check@v1"}
    for name, spec in SPECS.items():
        if name in read_only:
            assert spec.requires_idempotency_key is False
        else:
            assert spec.requires_idempotency_key is True
