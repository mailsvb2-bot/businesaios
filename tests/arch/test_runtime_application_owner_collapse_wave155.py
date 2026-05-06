from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def test_runtime_application_package_root_exports_contract_and_crm_surfaces() -> None:
    text = _read("runtime/application/__init__.py")
    assert "CANON_RUNTIME_APPLICATION_PACKAGE_OWNER = True" in text
    assert "from runtime.application.contracts import (" in text
    assert "from runtime.application.crm_contracts import RuntimeCrmContracts" in text
    assert "from runtime.application.crm_service import RuntimeCrmService" in text


def test_runtime_modules_prefer_runtime_application_package_root() -> None:
    relpaths = [
        "boot/runtime_integration.py",
        "runtime/domain_ports.py",
        "runtime/capability_access.py",
        "runtime/read_only_registry.py",
        "runtime/typed_access.py",
        "runtime/service_exports.py",
        "runtime/ceo/__init__.py",
        "runtime/bootstrap/runtime_builder.py",
        "runtime/bootstrap/startup_validator.py",
        "core/decision/__init__.py",
    ]
    direct_contract_modules = {
        "runtime/domain_ports.py",
        "runtime/capability_access.py",
        "runtime/read_only_registry.py",
        "runtime/typed_access.py",
        "runtime/service_exports.py",
        "runtime/ceo/__init__.py",
        "runtime/bootstrap/runtime_builder.py",
        "runtime/bootstrap/startup_validator.py",
    }
    direct_owner_modules = {
        "core/decision/__init__.py",
    }
    for relpath in relpaths:
        text = _read(relpath)
        if relpath in direct_contract_modules:
            assert "from runtime.application.contracts import " in text, relpath
        elif relpath in direct_owner_modules:
            assert "application.decision" in text, relpath
        else:
            assert "from runtime.application import " in text, relpath
            assert "from runtime.application.contracts import " not in text, relpath
