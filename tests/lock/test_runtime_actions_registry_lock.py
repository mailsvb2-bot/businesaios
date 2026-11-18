from __future__ import annotations

from pathlib import Path

import pytest

from runtime.boot.actions_catalog import EFFECT_ONLY_ACTIONS
from runtime.boot.actions_registry import INLINE_ALLOWLIST, SPECS, all_actions
from runtime.boot.registration_manifest import registered_action_names


@pytest.mark.lock
def test_actions_registry_matches_boot_registration_manifest():
    expected = all_actions()
    registered = set(registered_action_names())
    assert registered == expected, f"registry drift: missing={sorted(expected-registered)} extra={sorted(registered-expected)}"


@pytest.mark.lock
def test_registered_actions_cannot_bypass_handler_wiring() -> None:
    assert EFFECT_ONLY_ACTIONS == frozenset()


@pytest.mark.lock
def test_no_unregistered_handlers_register_calls_anywhere():
    """Forbid introducing a new runtime-action without updating the canonical registry."""
    expected = all_actions()
    offenders: list[str] = []
    import re
    from pathlib import Path
    for p in Path("runtime").rglob("*.py"):
        txt = p.read_text(encoding="utf-8")
        for action in re.findall(r'handlers\.register\(\s*"([^"]+)"', txt):
            if action not in expected:
                offenders.append(f"{p}:{action}")
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
def test_every_action_has_closed_verification_contract():
    allowed_categories = {
        "external_effect",
        "external_best_effort",
        "internal_bookkeeping",
        "advisory",
    }
    allowed_modes = {"required", "conditional", "not_required"}

    for name, spec in SPECS.items():
        assert spec.execution_category in allowed_categories, f"unknown execution category: {name}={spec.execution_category}"
        assert spec.external_confirmation_mode in allowed_modes, f"unknown confirmation mode: {name}={spec.external_confirmation_mode}"
        if spec.external_confirmation_mode == "required":
            assert spec.execution_category == "external_effect", f"required confirmation on non-external action: {name}"
        if spec.external_confirmation_mode == "conditional":
            assert spec.execution_category == "external_effect", f"conditional confirmation on non-external action: {name}"
        if spec.execution_category == "external_best_effort":
            assert spec.external_confirmation_mode == "not_required", f"best-effort action became blocking: {name}"


@pytest.mark.lock
def test_idempotency_requirement_is_explicit_and_consistent():
    read_only = {"noop@v1", "poll_telegram_updates@v1", "telegram_self_check@v1"}
    for name, spec in SPECS.items():
        if name in read_only:
            assert spec.requires_idempotency_key is False
        else:
            assert spec.requires_idempotency_key is True

@pytest.mark.lock
def test_yookassa_webhook_server_has_one_canonical_owner():
    """Only the sealed client module may own the HTTP server implementation."""
    root = Path(__file__).resolve().parents[2]
    canonical = root / "runtime" / "_internal" / "effects_clients" / "yookassa_webhook_server.py"
    legacy = root / "runtime" / "_internal" / "_effects_impl.py"
    canonical_source = canonical.read_text(encoding="utf-8")
    assert "def start_yookassa_webhook_server_in_thread" in canonical_source
    assert "payment_outbox.enqueue_once" in canonical_source
    assert "HTTPServer((" in canonical_source
    legacy_source = legacy.read_text(encoding="utf-8")
    assert "def start_yookassa_webhook_server_in_thread" not in legacy_source

    allowed_references = {
        "runtime/_internal/effects_clients/yookassa_webhook_server.py",
        "runtime/_internal/effects_actions/payments/yookassa.py",
        "runtime/_internal/effects_actions/payments_actions.py",
        "runtime/_internal/effects_servers.py",
        "runtime/boot_impl/telegram_runner.py",
        "runtime/effects/__init__.py",
    }
    references = set()
    implementation_owners = set()
    for package in (
        "application", "canon", "config", "contracts", "core",
        "crm", "integration_observations", "interfaces", "market_intelligence",
        "runtime", "scripts",
    ):
        package_root = root / package
        if not package_root.is_dir():
            continue
        for source in package_root.rglob("*.py"):
            try:
                text = source.read_text(encoding="utf-8")
            except OSError:
                continue
            if "start_yookassa_webhook_server_in_thread" in text:
                relative = source.relative_to(root).as_posix()
                references.add(relative)
                if "payment_outbox.enqueue_once" in text and "HTTPServer((" in text:
                    implementation_owners.add(relative)
    assert references == allowed_references, f"unexpected YooKassa server reference: {sorted(references ^ allowed_references)}"
    assert implementation_owners == {"runtime/_internal/effects_clients/yookassa_webhook_server.py"}

    assert "effects_clients.yookassa_webhook_server" in (root / "runtime/_internal/effects_servers.py").read_text(encoding="utf-8")
    assert "effects_clients.yookassa_webhook_server" in (root / "runtime/_internal/effects_actions/payments/yookassa.py").read_text(encoding="utf-8")
    assert "start_webhook_server" in (root / "runtime/_internal/effects_actions/payments_actions.py").read_text(encoding="utf-8")
    assert "from runtime.effects import start_yookassa_webhook_server_in_thread" in (root / "runtime/boot_impl/telegram_runner.py").read_text(encoding="utf-8")
    assert "_start_yookassa_webhook_server_in_thread" in (root / "runtime/effects/__init__.py").read_text(encoding="utf-8")
