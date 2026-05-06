from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_runtime_orchestrator_stays_readiness_only_without_alt_entrypoints() -> None:
    text = _read('runtime/runtime_orchestrator.py')
    assert 'CANON_RUNTIME_ROOT_READINESS_OWNER = True' in text
    assert 'CANON_RUNTIME_ROOT_NO_ASSEMBLY = True' in text
    assert 'compose_runtime(' not in text
    assert 'build_runtime(' not in text
    assert 'bootstrap_runtime(' not in text
    assert 'ServiceRegistry(' not in text
    assert 'ComponentRegistry(' not in text


def test_runtime_bootstrap_and_runtime_boot_do_not_become_root_assembly_surfaces() -> None:
    bootstrap_text = _read('runtime/bootstrap.py')
    runtime_boot_text = _read('runtime/runtime_boot.py')
    assert 'CANON_RUNTIME_BOOTSTRAP_PROCESS_ONLY = True' in bootstrap_text
    assert 'CANON_NO_ROOT_ASSEMBLY_LOGIC = True' in runtime_boot_text
    assert 'from boot.' not in bootstrap_text
    assert 'import boot.' not in bootstrap_text
    assert 'compose_runtime(' not in bootstrap_text
    assert 'register_service(' not in bootstrap_text
    assert 'register_component(' not in bootstrap_text
    assert '_load_sovereign_bootstrap_runtime' in runtime_boot_text
    assert 'import_module("runtime.bootstrap.sovereign_bootstrap")' in runtime_boot_text
    assert 'getattr(import_module("runtime.bootstrap.sovereign_bootstrap"), "bootstrap_runtime")' in runtime_boot_text
    assert 'bootstrap_runtime().artifacts.registry' not in runtime_boot_text
