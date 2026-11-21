"""IRON hardening suite (51 tests).

These tests are designed to be:
  - deterministic
  - hermetic (no network / no subprocess)
  - focused on Ring invariants and regression prevention
"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Helpers


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse(path: pathlib.Path) -> ast.AST:
    return ast.parse(_read(path), filename=str(path))


def _iter_prod_py() -> list[pathlib.Path]:
    excluded = {
        ".git",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "canon",
        "ci",
        "data",
        "dist",
        "docs",
        "env",
        "experimental",
        "node_modules",
        "scripts",
        "site-packages",
        "tests",
        "venv",
    }
    files: list[pathlib.Path] = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        rel_parts = rel.split("/")
        if rel.startswith("runtime/platform/support/"):
            continue
        if any(part in excluded for part in rel_parts):
            continue
        files.append(p)
    return files


def _find_imports(path: pathlib.Path) -> set[str]:
    tree = _parse(path)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.add(n.name)
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


# ---------------------------------------------------------------------------
# 1) Decision sovereignty + semantic safety (10)


def test_iron_01_decision_core_file_exists():
    assert (ROOT / "core" / "ai" / "decision_core.py").exists()


def test_iron_02_only_one_decide_def_in_prod():
    offenders: list[str] = []
    for p in _iter_prod_py():
        tree = _parse(p)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "decide":
                rel = p.relative_to(ROOT).as_posix()
                if rel.startswith("interfaces/messaging_runtime/"):
                    continue
                if rel.startswith("core/experiments/"):
                    continue
                if rel.startswith("runtime/messaging_policy_alert_dedup/"):
                    continue
                if rel.startswith("runtime/boot/decision_core_contract.py"):
                    continue
                if p != ROOT / "core" / "ai" / "decision_core.py":
                    offenders.append(str(p))
    assert not offenders


def test_iron_03_no_policy_class_named_decision_core():
    # Prevent semantic confusion by naming.
    offenders: list[str] = []
    for p in _iter_prod_py():
        tree = _parse(p)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.lower() == "decisioncore":
                if p != ROOT / "core" / "ai" / "decision_core.py":
                    offenders.append(f"{p}:{node.lineno}")
    assert not offenders


def test_iron_04_main_is_only_root_entrypoint():
    # Guard against accidental new entrypoints (common bypass vector).
    root_py = {p.name for p in ROOT.glob("*.py")}
    assert "main.py" in root_py
    assert "app.py" not in root_py
    assert "run.py" not in root_py


def test_iron_05_no_side_effects_on_import_bootstrap_location():
    # Ensure bootstrapping lives in runtime/bootstrap.py (not in sitecustomize).
    assert (ROOT / "runtime" / "bootstrap.py").exists()


def test_iron_06_sitecustomize_has_no_runtime_side_effects():
    p = ROOT / "sitecustomize.py"
    if not p.exists():
        return
    txt = _read(p)
    assert "open(" not in txt
    assert "requests" not in txt


def test_iron_07_usercustomize_has_no_runtime_side_effects():
    p = ROOT / "usercustomize.py"
    if not p.exists():
        return
    txt = _read(p)
    assert "open(" not in txt
    assert "requests" not in txt


def test_iron_08_executor_is_only_private_effects_importer():
    offenders: list[str] = []
    for p in _iter_prod_py():
        if p in (ROOT / "runtime" / "executor.py", ROOT / "runtime" / "effects.py"):
            continue
        if "runtime._internal._effects_impl" in _read(p):
            offenders.append(str(p))
    assert not offenders


def test_iron_09_no_requests_outside_effects_impl_and_tests():
    offenders: list[str] = []
    for p in _iter_prod_py():
        if p == ROOT / "runtime" / "_internal" / "_effects_impl.py":
            continue
        imps = _find_imports(p)
        if any(i.split(".")[0] in {"requests", "httpx", "aiohttp", "socket"} for i in imps):
            offenders.append(str(p))
    assert not offenders


def test_iron_10_no_subprocess_outside_effects_impl():
    offenders: list[str] = []
    for p in _iter_prod_py():
        if p == ROOT / "runtime" / "_internal" / "_effects_impl.py":
            continue
        imps = _find_imports(p)
        if any(i.split(".")[0] in {"subprocess", "os"} and "_effects_impl" not in str(p) for i in imps):
            # os is allowed widely; we only forbid known process-spawn patterns elsewhere via other tests.
            if any(i.split(".")[0] == "subprocess" for i in imps):
                offenders.append(str(p))
    assert not offenders


# ---------------------------------------------------------------------------
# 2) Executor claim/proof invariants (10)


def test_iron_11_executor_checks_claim_return_value():
    executor = _read(ROOT / "runtime" / "executor.py")
    stages = _read(ROOT / "runtime" / "execution" / "executor_stages.py")
    assert "def _claim_or_skip_outbox" in executor
    assert "if not executor._claim_or_skip_outbox(env):" in stages


def test_iron_12_executor_returns_already_claimed_status():
    txt = _read(ROOT / "runtime" / "executor.py")
    assert "already_claimed" in txt


def test_iron_13_executor_uses_public_has_event_api():
    txt = _read(ROOT / "runtime" / "executor.py")
    assert ".has_event(" in txt
    # Ensure we never access event_log._store or getattr(self._events, "_store").
    assert "._store" not in txt
    assert "getattr(self._events, \"_store\"" not in txt


def test_iron_14_executor_uses_proof_registry_mapping():
    txt = _read(ROOT / "runtime" / "executor.py")
    assert "ACTION_PROOF_EVENT" in txt


def test_iron_15_proof_registry_file_exists():
    assert (ROOT / "core" / "actions" / "proof_registry.py").exists()


def test_iron_16_proof_registry_contains_core_actions():
    from core.actions.proof_registry import ACTION_PROOF_EVENT

    assert "send_message@v1" in ACTION_PROOF_EVENT
    assert "capture_payment@v1" in ACTION_PROOF_EVENT


def test_iron_17_executor_marks_delivered_on_already_executed():
    txt = _read(ROOT / "runtime" / "executor.py")
    assert "mark_delivered" in txt
    assert "already_executed" in txt


def test_iron_18_event_log_has_event_exists():
    from core.events.log import EventLog

    assert hasattr(EventLog, "has_event")


def test_iron_19_event_log_iter_events_exists():
    from core.events.log import EventLog

    assert hasattr(EventLog, "iter_events")


def test_iron_20_event_log_has_event_works_on_list_store():
    from core.events.log import EventLog

    store: list[dict] = []
    log = EventLog(store, tenant="default")
    log.emit(event_type="message_sent", source="t", user_id="u", payload={}, decision_id="d1", correlation_id="c")
    assert log.has_event("d1", "message_sent") is True
    assert log.has_event("d2", "message_sent") is False


# ---------------------------------------------------------------------------
# 3) Outbox / dead-letter / retries (10)


def test_iron_21_sqlite_outbox_has_max_retries_constant():
    txt = _read(ROOT / "runtime" / "platform" / "outbox" / "sqlite_outbox.py")
    assert "MAX_RETRIES" in txt


def test_iron_22_sqlite_outbox_moves_to_dead_letter():
    txt = _read(ROOT / "runtime" / "platform" / "outbox" / "sqlite_outbox.py")
    assert "move_to_dead_letter" in txt


def test_iron_23_outbox_retry_module_exists():
    assert (ROOT / "runtime" / "platform" / "outbox" / "retry.py").exists()


def test_iron_24_outbox_retry_has_max_retries():
    txt = _read(ROOT / "runtime" / "platform" / "outbox" / "retry.py")
    assert "MAX_RETRIES" in txt


def test_iron_25_outbox_retry_moves_to_dead_letter():
    txt = _read(ROOT / "runtime" / "platform" / "outbox" / "retry.py")
    assert "move_to_dead_letter" in txt


def test_iron_26_delivery_state_module_exists():
    assert (ROOT / "runtime" / "platform" / "delivery_state.py").exists()


def test_iron_27_effects_impl_uses_delivery_state():
    txt = _read(ROOT / "runtime" / "_internal" / "_effects_impl.py")
    assert "delivery_state" in txt or "mark_delivered" in txt


def test_iron_28_outbox_has_claim_api():
    # Both sqlite and postgres outboxes should expose claim.
    for p in [
        ROOT / "runtime" / "platform" / "outbox" / "sqlite_outbox.py",
        ROOT / "runtime" / "platform" / "outbox" / "postgres_outbox.py",
    ]:
        if p.exists():
            assert "def claim" in _read(p)


def test_iron_29_outbox_has_status_api():
    p = ROOT / "runtime" / "platform" / "outbox" / "sqlite_outbox.py"
    assert "def status" in _read(p)


def test_iron_30_outbox_has_pending_api():
    p = ROOT / "runtime" / "platform" / "outbox" / "sqlite_outbox.py"
    assert "def has_pending" in _read(p)


# ---------------------------------------------------------------------------
# 4) Payments reconciliation + idempotency (10)


def test_iron_31_provider_has_no_network_imports():
    imps = _find_imports(ROOT / "core" / "payments" / "provider.py")
    assert not any(i.split(".")[0] in {"requests", "aiohttp", "httpx"} for i in imps)


def test_iron_32_idempotence_key_stable():
    from core.payments.provider import idempotence_key_for_order

    assert idempotence_key_for_order("123") == "order-123"
    assert idempotence_key_for_order(" 123 ") == "order-123"


def test_iron_33_idempotence_key_rejects_empty():
    import pytest

    from core.payments.provider import idempotence_key_for_order

    with pytest.raises(ValueError):
        idempotence_key_for_order(" ")


def test_iron_34_canonical_reconciliation_is_pure_no_network_imports():
    path = ROOT / "runtime" / "_internal" / "effects_actions" / "payments" / "reconciliation.py"
    tree = _parse(path)
    forbidden = {"requests", "httpx", "aiohttp", "urllib3"}
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert not (imports & forbidden)


def test_iron_35_canonical_terminal_payment_event_is_idempotent():
    from types import SimpleNamespace

    from runtime._internal.effects_actions.payments.reconciliation import _emit_terminal_event_once

    class EventLog:
        def __init__(self):
            self.events = []

        def iter_events(self):
            return iter(self.events)

        def emit(self, **event):
            self.events.append(event)

    effects = SimpleNamespace(event_log=EventLog())
    args = {
        "event_type": "payment_succeeded",
        "source": "payments",
        "user_id": "user-a",
        "decision_id": "decision-a",
        "correlation_id": "correlation-a",
        "original_decision_id": "decision-a",
        "external_id": "payment-a",
        "payload": {"status": "succeeded"},
    }
    first = _emit_terminal_event_once(effects, **args)
    second = _emit_terminal_event_once(effects, **args)
    assert first == second
    assert len(effects.event_log.events) == 1
    assert effects.event_log.events[0]["event_id"] == first


def test_iron_36_canonical_reconciliation_checks_tenant_before_reading_events(monkeypatch):
    import pytest
    from types import SimpleNamespace

    from runtime._internal.effects_actions.payments import reconciliation

    class EventLog:
        def iter_events(self):
            raise AssertionError("foreign tenant must be rejected before event enumeration")

    monkeypatch.setattr(reconciliation, "assert_called_from_executor", lambda: None)

    def reject_foreign_tenant(event_log, *, tenant_id, operation):
        assert tenant_id == "tenant-foreign"
        assert operation == "reconcile_payments"
        raise RuntimeError("payment tenant scope rejected")

    monkeypatch.setattr(reconciliation, "assert_event_log_tenant", reject_foreign_tenant)
    effects = SimpleNamespace(event_log=EventLog(), ledger=object())
    with pytest.raises(RuntimeError, match="tenant scope rejected"):
        reconciliation.reconcile_payments_effect(
            effects,
            decision_id="decision-a",
            correlation_id="correlation-a",
            tenant_id="tenant-foreign",
            business_id="business-a",
        )


def test_iron_37_effects_impl_payment_uses_idempotence_key_logic_in_core():
    # Ensure runtime uses core idempotence key helper (or equivalent stable form).
    txt = _read(ROOT / "runtime" / "_internal" / "_effects_impl.py")
    assert "idempot" in txt.lower()


def test_iron_38_no_payment_provider_network_in_core_tree():
    offenders: list[str] = []
    for p in (ROOT / "core").rglob("*.py"):
        imps = _find_imports(p)
        if any(i.split(".")[0] in {"requests", "httpx", "aiohttp"} for i in imps):
            offenders.append(str(p))
    assert not offenders


def test_iron_39_canonical_payment_reconciler_consumes_created_events():
    from runtime._internal.effects_actions.payments import reconciliation

    assert "payment_created" in _read(pathlib.Path(reconciliation.__file__))
    assert callable(reconciliation.reconcile_payments_effect)


def test_iron_40_canonical_payment_reconcile_window_is_bounded():
    import inspect

    from runtime._internal.effects_actions.payments.reconciliation import reconcile_payments_effect

    assert inspect.signature(reconcile_payments_effect).parameters["window_min"].default == 30


# ---------------------------------------------------------------------------
# 5) Governance + ring health + reward invariants (10)


def test_iron_41_reward_engine_requires_proof_registry_mapping():
    txt = _read(ROOT / "core" / "reward" / "reward_engine.py")
    assert "ACTION_PROOF_EVENT" in txt


def test_iron_42_reward_engine_early_returns_without_proof():
    txt = _read(ROOT / "core" / "reward" / "reward_engine.py")
    assert "return 0.0" in txt


def test_iron_43_delayed_reward_module_exists():
    assert (ROOT / "core" / "reward" / "delayed.py").exists()


def test_iron_44_governance_version_constant_exists():
    p = ROOT / "governance" / "version.py"
    assert p.exists()
    assert "CONSTITUTION_VERSION" in _read(p)


def test_iron_45_time_scale_matrix_exists():
    p = ROOT / "governance" / "time_scale.py"
    assert p.exists()
    txt = _read(p)
    assert "assert_action_allowed" in txt


def test_iron_46_ring_health_file_exists():
    assert (ROOT / "ops" / "health_ring.py").exists()


def test_iron_47_ring_health_returns_all_ports():
    from ops.health_ring import ring_health

    class P:
        def ping(self):
            return True

    out = ring_health(P(), P(), P())
    assert set(out.keys()) == {"event_log", "ledger", "outbox"}


def test_iron_48_ring_health_is_hermetic_no_imports():
    # This module should not import runtime/handlers/effects.
    txt = _read(ROOT / "ops" / "health_ring.py")
    assert "runtime" not in txt
    assert "handlers" not in txt


def test_iron_49_action_proof_registry_is_single_source_of_truth():
    # Ensure executor and reward do not embed their own mapping dicts.
    executor_txt = _read(ROOT / "runtime" / "executor.py")
    reward_txt = _read(ROOT / "core" / "reward" / "reward_engine.py")
    assert "policy_deployed" not in executor_txt or "ACTION_PROOF_EVENT" in executor_txt
    assert "policy_deployed" not in reward_txt or "ACTION_PROOF_EVENT" in reward_txt


def test_iron_50_no_private_event_store_access_from_executor():
    txt = _read(ROOT / "runtime" / "executor.py")
    assert "._store" not in txt
    assert "getattr(self._events, \"_store\"" not in txt

def test_iron_51_billing_ledger_rejects_non_integer_minor_units():
    from billing.ledger_event import LedgerEntry

    LedgerEntry("tenant", "entry", "billing.accounts.expense", "debit", 1, "USD", "llm_usage", "request-1").validate()
    for amount in (True, 1.5, "1"):
        try:
            LedgerEntry("tenant", "entry", "billing.accounts.expense", "debit", amount, "USD", "llm_usage", "request-1").validate()
        except ValueError:
            continue
        raise AssertionError("non-integer ledger minor amount was accepted")
