from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_runtime_bootstrap_stays_process_only_and_not_boot_owner_clone() -> None:
    text = _read("runtime/bootstrap.py")
    assert "CANON_RUNTIME_BOOTSTRAP_PROCESS_ONLY = True" in text
    assert "from runtime.bootstrap.process_bootstrap import run_process_bootstrap" in text
    assert "def _load_sovereign_bootstrap()" in text
    assert "from boot." not in text
    assert "import boot." not in text


def test_runtime_runtime_boot_stays_thin_wrapper_without_root_assembly_logic() -> None:
    text = _read("runtime/runtime_boot.py")
    assert "CANON_COMPAT_SHIM = True" in text
    assert "CANON_NO_ROOT_ASSEMBLY_LOGIC = True" in text
    assert "runtime.bootstrap.sovereign_bootstrap" in text
    assert "from runtime.bootstrap import bootstrap_runtime" not in text
    assert "def _load_sovereign_bootstrap_runtime()" in text
    assert "compose_runtime(" not in text
    assert "build_runtime_boot_surface(" not in text
    assert "_load_sovereign_bootstrap_runtime()().artifacts.registry" in text


def test_runtime_guard_stays_single_fail_closed_gate_without_decision_calls() -> None:
    text = _read("runtime/guard.py")
    assert "CANON_RUNTIME_GUARD_OWNER = True" in text
    assert "CANON_FAIL_CLOSED_EXECUTION_GATE = True" in text
    assert ".issue(" not in text
    assert "compose_runtime(" not in text
