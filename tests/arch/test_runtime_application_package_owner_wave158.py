from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def test_runtime_application_package_root_declares_public_api_as_compat_alias() -> None:
    root_text = _read("runtime/application/__init__.py")
    manifest_text = _read("runtime/canonical_surface_manifest.py")
    assert "CANON_RUNTIME_APPLICATION_PACKAGE_OWNER = True" in root_text
    assert '"runtime.application",' in manifest_text
    assert '"runtime.application.public_api",' in manifest_text


def test_internal_runtime_code_avoids_runtime_application_public_api_surface() -> None:
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
        "core/decision/__init__.py",
    ]
    for relpath in relpaths:
        text = _read(relpath)
        assert "from runtime.application.public_api import " not in text, relpath
