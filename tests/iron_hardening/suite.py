from __future__ import annotations

"""IRON hardening suite (50 tests).

These tests are designed to be:
  - deterministic
  - hermetic (no network / no subprocess)
  - focused on Ring invariants and regression prevention
"""

import ast
import pathlib
from datetime import datetime, timezone, UTC

ROOT = pathlib.Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Helpers


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse(path: pathlib.Path) -> ast.AST:
    return ast.parse(_read(path), filename=str(path))


def _iter_prod_py() -> list[pathlib.Path]:
    excluded = {"tests", "experimental", "docs", "ci", ".github", "data", "scripts", "canon"}
    files: list[pathlib.Path] = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith("runtime/platform/support/"):
            continue
        if any(part in excluded for part in p.parts):
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
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "decide":
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
    txt = _read(ROOT / "runtime" / "executor.py")
    assert "claimed =" in txt
    assert "if not claimed" in txt


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


def test_iron_34_reconcile_module_is_pure_no_requests():
    txt = _read(ROOT / "core" / "payments" / "reconcile.py")
    assert "requests" not in txt


def test_iron_35_reconcile_counts_reconciled_records():
    from core.payments.reconcile import reconcile_pending_payments

    class ES:
        def __init__(self, events):
            self._events = events

        def iter_events(self, *, tenant_id=None, start_ms=0, end_ms=None, event_type=None):
            for e in self._events:
                if event_type is None or e.get("event_type") == event_type:
                    yield e

    class L:
        def __init__(self):
            self.ok = []
            self.bad = []

        def mark_effect_completed(self, envelope_id: str) -> None:
            self.ok.append(envelope_id)

        def mark_effect_failed(self, envelope_id: str) -> None:
            self.bad.append(envelope_id)

    class P:
        def __init__(self, mapping):
            self.mapping = mapping

        def get_payment_status(self, *, external_payment_id: str) -> str:
            return self.mapping.get(external_payment_id, "pending")

    now = datetime.now(tz=UTC)
    es = ES([
        {"event_type": "payment_created", "payload": {"external_id": "p1"}, "decision_id": "d1"},
        {"event_type": "payment_created", "payload": {"external_id": "p2"}, "decision_id": "d2"},
        {"event_type": "payment_created", "payload": {"external_id": "p3"}, "decision_id": "d3"},
    ])
    ledger = L()
    payments = P({"p1": "succeeded", "p2": "canceled", "p3": "pending"})
    n = reconcile_pending_payments(now=now, event_store=es, ledger=ledger, payments=payments)
    assert n == 2
    assert ledger.ok == ["d1"]
    assert ledger.bad == ["d2"]


def test_iron_36_reconcile_skips_missing_ids():
    from core.payments.reconcile import reconcile_pending_payments

    class ES:
        def iter_events(self, *, tenant_id=None, start_ms=0, end_ms=None, event_type=None):
            yield {"event_type": "payment_created", "payload": {}, "decision_id": "d1"}
            yield {"event_type": "payment_created", "payload": {"external_id": "p1"}}

    class L:
        def mark_effect_completed(self, envelope_id: str) -> None:
            raise AssertionError("should not be called")

        def mark_effect_failed(self, envelope_id: str) -> None:
            raise AssertionError("should not be called")

    class P:
        def get_payment_status(self, *, external_payment_id: str) -> str:
            return "succeeded"

    now = datetime.now(tz=UTC)
    n = reconcile_pending_payments(now=now, event_store=ES(), ledger=L(), payments=P())
    assert n == 0


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


def test_iron_39_payment_created_event_schema_exists():
    # Proof that payment orchestration can emit canonical event types.
    # We simply ensure the string is referenced in code (schema registry may live elsewhere).
    txt = _read(ROOT / "core" / "payments" / "reconcile.py")
    assert "payment_created" in txt


def test_iron_40_payment_reconcile_window_constant_is_int():
    from core.payments.reconcile import RECONCILE_WINDOW_MIN

    assert isinstance(RECONCILE_WINDOW_MIN, int)
    assert RECONCILE_WINDOW_MIN > 0


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
