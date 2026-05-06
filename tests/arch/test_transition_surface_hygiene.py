from __future__ import annotations

from pathlib import Path

from canon.transition_surfaces import TRANSITION_CANONICAL_TARGETS, TRANSITION_SURFACE_MODULES

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_transition_surfaces_are_explicitly_marked() -> None:
    for rel in TRANSITION_SURFACE_MODULES:
        text = _read(rel)
        assert "CANON_TRANSITION_SURFACE = True" in text, rel
        if "CANON_COMPAT_SHIM" in text or "NON_CANON_COMPAT_NAMESPACE" in text:
            assert "__all__" in text, rel


def test_no_architecture_or_unit_test_uses_transition_hold_marker() -> None:
    offenders: list[str] = []
    for path in ROOT.joinpath("tests").rglob("test_*.py"):
        if "quarantine" in path.name.lower():
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, f"quarantine test naming survived: {offenders}"


def test_learning_transition_surfaces_are_explicit_marked_reexports() -> None:
    for rel, canonical in TRANSITION_CANONICAL_TARGETS.items():
        text = _read(rel)
        assert "CANON_COMPAT_SHIM = True" in text, rel
        assert canonical in text, rel
        assert "Compatibility re-export" in text, rel


def test_learning_transition_surfaces_stay_tiny() -> None:
    for rel in TRANSITION_CANONICAL_TARGETS:
        lines = [line for line in _read(rel).splitlines() if line.strip()]
        assert len(lines) <= 10, f"transition surface must stay tiny: {rel}"


def test_selected_shim_surfaces_use_explicit_exports_only() -> None:
    files = (
        "runtime/platform/event_store/contract.py",
        "runtime/platform/config/__init__.py",
        "core/survival/__init__.py",
        "core/contracts/autopilot_contract.py",
        "core/pricing/stop_loss.py",
        "core/retention/event_types.py",
    )
    for rel in files:
        text = _read(rel)
        assert "import *" not in text, f"wildcard import remains in {rel}"
        assert "__all__" in text, f"explicit export surface missing in {rel}"
