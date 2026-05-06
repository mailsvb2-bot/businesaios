from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ROOT_RUNTIME_SURFACES = {
    "runtime/bootstrap.py": {"boot", "runtime.executor", "decision_core", "compose_runtime"},
    "runtime/runtime_boot.py": {"boot", "runtime.executor", "decision_core", "compose_runtime"},
    "runtime/runtime_orchestrator.py": {"runtime.executor", "decision_core", "boot.factories"},
    "runtime/recovery.py": {"decision_core", "boot.factories"},
    "runtime/guard.py": {"decision_core", "compose_runtime"},
}


def _imports(relative: str) -> set[str]:
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level + (node.module or "")
            values.add(prefix)
    return values



def test_runtime_root_surfaces_keep_forbidden_imports_out() -> None:
    for relative, forbidden in ROOT_RUNTIME_SURFACES.items():
        imports = _imports(relative)
        for bad in forbidden:
            assert all(not (imported == bad or imported.startswith(f"{bad}.")) for imported in imports), f"{relative} must not import {bad}; got {sorted(imports)}"



def test_runtime_critical_factories_is_lazy_shim() -> None:
    text = (ROOT / "runtime/critical_factories.py").read_text(encoding="utf-8")
    assert "CANON_LAZY_IMPORT_SHIM = True" in text
    assert "from boot.factories" not in text
    assert "import_module(module_name)" in text


def test_runtime_critical_factories_use_package_owner_surface() -> None:
    text = (ROOT / "runtime/critical_factories.py").read_text(encoding="utf-8")
    assert 'CANON_CRITICAL_FACTORIES_PACKAGE_OWNER = "boot.factories"' in text
    assert '("boot.factories", "build_decision_core")' in text
    assert '("boot.factories", "build_runtime_decision_execution_service")' in text
    assert 'decision_core_factory' not in text
