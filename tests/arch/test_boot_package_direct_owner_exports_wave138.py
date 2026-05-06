from __future__ import annotations

from pathlib import Path


def _read(rel: str) -> str:
    return Path(rel).read_text(encoding="utf-8")


def test_boot_package_exports_direct_owner_surfaces() -> None:
    text = _read("boot/__init__.py")
    assert 'CANON_BOOT_PACKAGE_OWNER = True' in text
    assert 'CANON_BOOT_PACKAGE_DIRECT_OWNER_EXPORTS = True' in text
    assert '"BuiltRuntime": ("runtime.bootstrap", "BuiltRuntime")' in text
    assert '"build_runtime": ("bootstrap.compose", "build_runtime")' in text
    assert '"boot_application": ("bootstrap.app_boot", "boot_application")' in text
    assert '"boot_http_app": ("bootstrap.http_boot_surface", "build_http_boot_surface")' in text
    assert 'boot.public_api' not in text


def test_boot_package_root_installs_public_api_alias() -> None:
    text = _read("boot/__init__.py")
    assert 'CANON_BOOT_PUBLIC_API_COMPAT_SHELL = True' in text
    assert 'CANON_BOOT_PUBLIC_API_DIRECT_OWNER_DELEGATION = True' in text
    assert 'install_public_api_alias(__name__)' in text
    assert 'runtime.bootstrap.sovereign_bootstrap' not in text
    assert not Path('boot/public_api.py').exists()


def test_sovereign_bootstrap_keeps_owner_imports_internal() -> None:
    text = _read("runtime/bootstrap/sovereign_bootstrap.py")
    assert 'CANON_SOVEREIGN_BOOTSTRAP_DIRECT_PROCESS_OWNER_IMPORT = True' in text
    assert 'def _process_bootstrap_owner():' in text
    assert 'from runtime.bootstrap.process_bootstrap import run_process_bootstrap' in text
    prefix = text.split('def _process_bootstrap_owner():', 1)[0]
    assert 'from runtime.bootstrap.process_bootstrap import run_process_bootstrap' not in prefix
