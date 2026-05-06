from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _module(path: str) -> ast.Module:
    return ast.parse((ROOT / path).read_text(encoding="utf-8"))


def test_root_runtime_registry_shims_do_not_use_wildcard_exports() -> None:
    for path in ("runtime/component_registry.py", "runtime/service_registry.py"):
        module = _module(path)
        wildcard = [
            node
            for node in ast.walk(module)
            if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names)
        ]
        assert wildcard == [], f"{path} must not use wildcard exports"



def test_root_runtime_critical_factories_stays_lazy_shim_only() -> None:
    text = (ROOT / "runtime/critical_factories.py").read_text(encoding="utf-8")
    assert "CANON_COMPAT_SHIM = True" in text
    assert "CANON_NO_ROOT_FACTORY_OWNERSHIP = True" in text
    assert "CANON_LAZY_IMPORT_SHIM = True" in text
    assert "from boot.factories" not in text
    assert "import_module(module_name)" in text



def test_runtime_public_api_alias_has_fail_closed_collision_guard() -> None:
    source = (ROOT / "runtime/public_api_alias.py").read_text(encoding="utf-8")
    assert "public api alias collision" in source
    assert "public api attribute collision" in source
