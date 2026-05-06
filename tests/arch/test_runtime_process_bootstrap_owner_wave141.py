from __future__ import annotations

from pathlib import Path

from canon.collapse_readiness import CORE_RUNTIME_COLLAPSED_SURFACES


def test_runtime_bootstrap_root_collapsed_to_internal_process_and_sovereign_owners() -> None:
    assert CORE_RUNTIME_COLLAPSED_SURFACES["runtime.bootstrap"] == (
        "runtime.bootstrap.process_bootstrap / runtime.bootstrap.sovereign_bootstrap"
    )


def test_sovereign_bootstrap_does_not_import_public_runtime_bootstrap_surface() -> None:
    text = Path("runtime/bootstrap/sovereign_bootstrap.py").read_text(encoding="utf-8")
    assert "import runtime.bootstrap as runtime_bootstrap_surface" not in text
    assert "from runtime.bootstrap import" not in text
    assert "from runtime.bootstrap.process_bootstrap import run_process_bootstrap" in text


def test_runtime_bootstrap_root_delegates_process_bootstrap_to_internal_owner() -> None:
    text = Path("runtime/bootstrap.py").read_text(encoding="utf-8")
    assert "from runtime.bootstrap.process_bootstrap import run_process_bootstrap" in text
    assert "apply_process_hygiene()" not in text
    assert "activate_import_firewall()" not in text
