from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _assert_pure_core_registry_alias(rel: str, *, allow_policy_factory: bool = False) -> None:
    source = _read(rel)
    tree = ast.parse(source)

    assert "CANON_COMPAT_SHIM = True" in source
    assert "from core.ai.policy_registry import PolicyRegistry" in source
    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    allowed_modules = {"__future__", "core.ai.policy_registry"}
    if allow_policy_factory:
        allowed_modules.add("runtime.platform.support.policy")
    assert imported_modules <= allowed_modules


def test_runtime_duplicate_decision_core_is_removed() -> None:
    assert not (ROOT / "runtime/platform/support/optimization/decision_core.py").exists()


def test_runtime_duplicate_decision_trace_is_removed() -> None:
    assert not (ROOT / "runtime/platform/support/explainability/decision_trace.py").exists()


def test_runtime_policy_registry_is_pure_core_alias() -> None:
    _assert_pure_core_registry_alias(
        "runtime/platform/support/policy/policy_registry.py"
    )


def test_runtime_policy_factory_imports_core_registry_directly() -> None:
    source = _read("runtime/platform/support/policy/policy_factory.py")
    _assert_pure_core_registry_alias(
        "runtime/platform/support/policy/policy_factory.py",
        allow_policy_factory=True,
    )
    assert "runtime.platform.support.policy.policy_registry" not in source
