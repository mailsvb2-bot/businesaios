from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_runtime_boot_surface_has_single_assembly_owner_and_thin_compat_shells() -> None:
    boot_text = _read('boot/runtime_boot.py')
    bootstrap_text = _read('bootstrap/runtime_boot.py')
    runtime_text = _read('runtime/runtime_boot.py')

    assert 'build_runtime_boot_surface(' in bootstrap_text
    assert 'RuntimeOrchestrator(' in bootstrap_text

    assert 'RuntimeOrchestrator(' not in runtime_text
    assert 'RuntimeOrchestrator(' not in boot_text
    assert 'import_module("bootstrap.runtime_boot")' in boot_text
    assert 'return getattr(_owner_module(), "build_runtime_boot_surface")(*args, **kwargs)' in boot_text
    assert 'import_module("runtime.bootstrap.sovereign_bootstrap")' in runtime_text
