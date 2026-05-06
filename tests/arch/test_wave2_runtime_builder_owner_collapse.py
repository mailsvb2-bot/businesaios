from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _wildcard_imports(relative: str) -> list[ast.ImportFrom]:
    module = ast.parse(_read(relative))
    return [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names)
    ]


def test_runtime_builder_owner_is_canonical_in_attestation_and_fixtures() -> None:
    fixture = _read("tests/bootstrap/test_attestation_store.py")
    owner = _read("runtime/bootstrap/bootstrap_attestation.py")
    assert "runtime.bootstrap.runtime_builder" in fixture
    assert "runtime.bootstrap.runtime_builder" in owner
    assert "runtime.bootstrap_pkg.runtime_builder" not in owner
    assert "boot.runtime_orchestrator" not in fixture


def test_boot_runtime_orchestrator_is_internal_shim_only() -> None:
    text = _read("boot/runtime_orchestrator.py")
    assert "CANON_RUNTIME_ASSEMBLY_THIN_SHIM = True" in text
    assert "CANON_RUNTIME_ASSEMBLY_NO_DIRECT_OWNER_EXPORTS = True" in text
    assert "registry.begin_registration(" not in text
    assert "load_runtime_manifest(" not in text
    assert "RuntimeRegistrationInvoker(" not in text
    assert "from runtime.bootstrap_pkg.runtime_builder import" not in text
    assert "from runtime.bootstrap.runtime_builder import RuntimeBuilder" in text


def test_runtime_bootstrap_support_surfaces_use_explicit_exports_only() -> None:
    for relative in (
        "runtime/bootstrap/runtime_builder.py",
        "runtime/bootstrap/dependency_wiring.py",
        "runtime/bootstrap/sovereign_bootstrap.py",
        "runtime/bootstrap/runtime_composition_root.py",
    ):
        text = _read(relative)
        assert "EXPLICIT_EXPORTS_ONLY = True" in text, relative
        assert _wildcard_imports(relative) == [], relative
