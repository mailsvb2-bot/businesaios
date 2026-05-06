from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_runtime_bootstrap_package_stays_explicit_public_surface() -> None:
    text = _read("runtime/bootstrap/__init__.py")
    assert "CANON_RUNTIME_BOOTSTRAP_PACKAGE_LAZY_EXPORTS = True" in text
    assert "from runtime.bootstrap.sovereign_bootstrap import bootstrap_runtime, get_bootstrapped_runtime" not in text
    assert "from runtime.bootstrap.crm_bootstrap import build_crm_service" not in text
    assert '"bootstrap_runtime": ("runtime.bootstrap.sovereign_bootstrap", "bootstrap_runtime")' in text
    assert '"build_crm_service": ("runtime.bootstrap.crm_bootstrap", "build_crm_service")' in text
    assert "runtime.bootstrap_pkg" not in text
    assert "registry.begin_registration(" not in text


def test_runtime_bootstrap_pkg_cluster_is_fully_removed() -> None:
    assert not (ROOT / "runtime/bootstrap_pkg").exists()
