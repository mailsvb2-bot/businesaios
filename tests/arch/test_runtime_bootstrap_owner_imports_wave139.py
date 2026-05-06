from __future__ import annotations

from pathlib import Path

from canon.collapse_readiness import CORE_RUNTIME_COLLAPSED_SURFACES


def test_runtime_bootstrap_submodules_are_self_owned_canonical_surfaces() -> None:
    assert CORE_RUNTIME_COLLAPSED_SURFACES["runtime.bootstrap.sovereign_bootstrap"] == "runtime.bootstrap.sovereign_bootstrap"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["runtime.bootstrap.runtime_builder"] == "runtime.bootstrap.runtime_builder"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["runtime.bootstrap.runtime_composition_root"] == "runtime.bootstrap.runtime_composition_root"


def test_runtime_bootstrap_root_imports_bootstrap_owner_directly() -> None:
    text = Path("runtime/bootstrap.py").read_text(encoding="utf-8")
    assert "from runtime.bootstrap.sovereign_bootstrap import" in text
    assert "from runtime.bootstrap_pkg.sovereign_bootstrap import" not in text
