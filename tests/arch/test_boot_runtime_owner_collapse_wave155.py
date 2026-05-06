from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def test_boot_compat_surfaces_delegate_to_runtime_bootstrap_package_root() -> None:
    relpaths = [
        "boot/runtime_public_api.py",
        "boot/facade.py",
        "boot/bootstrap.py",
        "boot/runtime_integration.py",
        "boot/__init__.py",
    ]
    for relpath in relpaths:
        text = _read(relpath)
        assert "runtime.bootstrap.sovereign_bootstrap" not in text, relpath

    assert '_load_attr("bootstrap.compose", "bootstrap")' in _read("boot/bootstrap.py")
    assert 'getattr(import_module("bootstrap.compose"), "build_runtime")' in _read("boot/runtime_public_api.py")
    assert '_load_attr("bootstrap.compose", "build_runtime")' in _read("boot/facade.py")
    assert 'getattr(import_module("runtime.bootstrap.sovereign_bootstrap"), "bootstrap_runtime")' in _read("runtime/runtime_boot.py")


def test_runtime_bootstrap_package_root_exposes_built_runtime_owner() -> None:
    text = _read("runtime/bootstrap/__init__.py")
    assert '"BuiltRuntime": ("runtime.bootstrap.runtime_builder", "BuiltRuntime")' in text


def test_legacy_boot_shims_stay_thin_and_do_not_reintroduce_runtime_assembly() -> None:
    app_text = _read("boot/app_boot.py")
    http_text = _read("boot/http_boot.py")
    integration_text = _read("boot/runtime_integration.py")

    assert "CANON_APP_BOOT_THIN_SHIM = True" in app_text
    assert "CANON_APP_BOOT_NO_RUNTIME_ASSEMBLY = True" in app_text
    assert 'build_runtime(' not in app_text
    assert 'compose_runtime(' not in app_text
    assert '_load_attr("bootstrap.app_boot_surface", "build_app_boot_surface")' in app_text

    assert "CANON_HTTP_BOOT_THIN_SHIM = True" in http_text
    assert "CANON_HTTP_BOOT_NO_RUNTIME_ASSEMBLY = True" in http_text
    assert "CANON_HTTP_BOOT_SINGLE_SURFACE_DELEGATION = True" in http_text
    assert 'build_runtime(' not in http_text
    assert 'compose_runtime(' not in http_text
    assert '_load_attr("bootstrap.http_boot_surface", "build_http_boot_surface")' in http_text

    assert "CANON_RUNTIME_INTEGRATION_OWNER = True" in integration_text
    assert "CANON_RUNTIME_INTEGRATION_NO_LEGACY_BOOT_REUSE = True" in integration_text
    assert "CANON_RUNTIME_INTEGRATION_DIRECT_OWNER_BOOTSTRAP = True" in integration_text
    assert 'from boot.runtime_public_api import' not in integration_text
