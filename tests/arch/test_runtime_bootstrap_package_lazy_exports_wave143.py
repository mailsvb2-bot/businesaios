from __future__ import annotations

from pathlib import Path


def test_runtime_bootstrap_package_is_lazy_thin_shim() -> None:
    text = Path("runtime/bootstrap/__init__.py").read_text(encoding="utf-8")
    assert "CANON_RUNTIME_BOOTSTRAP_PACKAGE_LAZY_EXPORTS = True" in text
    assert "from runtime.bootstrap.crm_bootstrap import build_crm_service" not in text
    assert '"build_crm_service": ("runtime.bootstrap.crm_bootstrap", "build_crm_service")' in text
    assert '"bootstrap_runtime": ("runtime.bootstrap.sovereign_bootstrap", "bootstrap_runtime")' in text


def test_runtime_bootstrap_module_exports_direct_process_delegation_marker() -> None:
    text = Path("runtime/bootstrap.py").read_text(encoding="utf-8")
    assert '"CANON_RUNTIME_BOOTSTRAP_DIRECT_PROCESS_OWNER_DELEGATION"' in text
