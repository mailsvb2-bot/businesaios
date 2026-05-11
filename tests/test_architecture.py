from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

# SDK / side-effect libraries that MUST NOT be imported outside the private effects impl.
FORBIDDEN_SDK_IMPORTS = {
    "yookassa",
    "aiogram",
    "telebot",
    "telegram",
    "requests",
    "httpx",
    "urllib",
    "socket",
    "subprocess",
}

# Files where such imports are allowed (sealed transport only)
ALLOWED_SDK_FILES = {
    "runtime/_internal/_effects_impl.py",
    "runtime/_internal/effects_clients/http_client.py",
    "scripts/ci/subprocess_io.py",
    "tests/test_seccomp.py",
    "tests/test_domain_fs_check_script_smoke.py",
    "tests/test_world_snapshot_ast_lock.py",
}

ALLOWED_SDK_PREFIXES = (
    "runtime/_internal/effects_clients/",
    "runtime/_internal/effects_actions/",
    "scripts/ci/",
    "scripts/dev/",
)

# sqlite3 is allowed ONLY in runtime.platform storage implementations.
SQLITE_ALLOWED_PREFIXES = (
    "runtime/platform/event_store/",
    "runtime/platform/outbox/",
    "observability/platform/decision_archive/",
    "runtime/platform/ledger/",
    "observability/platform/snapshot_store/",
    "runtime/platform/behavior_graph/",
    "runtime/platform/delivery_state.py",
    "runtime/platform/security_sqlite_stores.py",
    "runtime/platform/billing_sqlite_store.py",
    "runtime/platform/billing_dispute_store.py",
    "runtime/platform/billing_recovery_store.py",
    "runtime/platform/billing_scheduler_job_store.py",
    "runtime/platform/safety_sqlite_migrations.py",
    "runtime/platform/safety_action_budget_ledger.py",
    "runtime/platform/safety_rollback_store.py",
    "runtime/platform/safety_runaway_loop_store.py",
    "runtime/platform/safety_approval_repository.py",
    "runtime/platform/safety_circuit_breaker_store.py",
    "runtime/platform/market_intelligence_state_store.py",
)


def _rel(py: pathlib.Path) -> str:
    return py.relative_to(ROOT).as_posix()


def _iter_py_files():
    for py in ROOT.rglob("*.py"):
        rel = _rel(py)
        if rel.startswith(".venv/"):
            continue
        yield py, rel


def _parse(py: pathlib.Path):
    return ast.parse(py.read_text(encoding="utf-8"), filename=str(py))


def test_no_private_internal_imports_outside_executor():
    for py, rel in _iter_py_files():
        # runtime/_internal is the sealed implementation zone; it is allowed to
        # import other runtime/_internal modules.
        if rel.startswith(("runtime/_internal/", "tests/")):
            continue
        if rel in ("runtime/executor.py", "runtime/effects.py", "tests/test_architecture.py"):
            continue
        tree = _parse(py)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        mod = n.name
                        assert not mod.startswith("runtime._internal"), f"Forbidden import of runtime._internal in {rel}: {mod}"
                else:
                    mod = node.module or ""
                    assert not mod.startswith("runtime._internal"), f"Forbidden import of runtime._internal in {rel}: {mod}"


def test_sdk_imports_only_in_private_effects_impl():
    for py, rel in _iter_py_files():
        if rel.startswith("tests/"):
            continue
        tree = _parse(py)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                bases = []
                if isinstance(node, ast.Import):
                    bases = [n.name.split(".")[0] for n in node.names]
                else:
                    if node.module:
                        bases = [node.module.split(".")[0]]
                for base in bases:
                    if base in FORBIDDEN_SDK_IMPORTS:
                        assert (rel in ALLOWED_SDK_FILES) or rel.startswith(ALLOWED_SDK_PREFIXES), (
                            f"SDK import '{base}' forbidden in {rel}; allowed only in {sorted(ALLOWED_SDK_FILES)} "
                            f"or under prefixes {ALLOWED_SDK_PREFIXES}"
                        )
                    if base == "sqlite3":
                        ok = rel.startswith(SQLITE_ALLOWED_PREFIXES)
                        assert ok, f"sqlite3 import forbidden in {rel}; allowed only in {SQLITE_ALLOWED_PREFIXES}"


def test_ledger_try_mark_executed_only_in_runtime_guard():
    for py, rel in _iter_py_files():
        if rel in ("runtime/guard.py", "tests/test_architecture.py"):
            continue
        tree = _parse(py)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "try_mark_executed":
                    raise AssertionError(f"Forbidden try_mark_executed() call in {rel}; must occur only in runtime/guard.py")


def test_runtime_modules_not_imported_in_core_layers():
    forbidden = {"runtime.executor", "runtime.guard", "runtime.handlers"}
    for py, rel in _iter_py_files():
        if rel.startswith(("runtime/", "tests/", "main.py")):
            continue
        tree = _parse(py)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if any(mod == f or mod.startswith(f + ".") for f in forbidden):
                    raise AssertionError(f"Forbidden import of runtime layer in {rel}: {mod}")
            if isinstance(node, ast.Import):
                for n in node.names:
                    mod = n.name
                    if any(mod == f or mod.startswith(f + ".") for f in forbidden):
                        raise AssertionError(f"Forbidden import of runtime layer in {rel}: {mod}")


def test_runtime_handlers_registry_no_business_logic_markers():
    # Heuristic but useful: runtime handler registry must not reference business domains.
    py = ROOT / "runtime" / "handlers" / "registry.py"
    txt = py.read_text(encoding="utf-8").lower()
    forbidden_markers = ["price", "discount", "offer", "ltv", "growth", "funnel", "upsell", "churn", "segment"]
    for m in forbidden_markers:
        assert m not in txt, f"Business marker '{m}' found in runtime/handlers/registry.py (Decision bypass risk)"


def test_runtime_handlers_is_package_not_shadow_module():
    assert (ROOT / "runtime" / "handlers" / "__init__.py").exists()
    assert not (ROOT / "runtime" / "handlers.py").exists()
