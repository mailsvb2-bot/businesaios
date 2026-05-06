from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_world_model_contract_has_canon_version_marker() -> None:
    path = ROOT / "runtime" / "boot" / "world_model_contract.py"
    text = path.read_text(encoding="utf-8")
    assert "class DecisionWorldModelPort" in text
    assert "WORLD_MODEL_CANON_VERSION" in text


def test_boot_core_assembly_keeps_decisioncore_wiring_local() -> None:
    path = ROOT / "runtime" / "boot" / "boot_core_assembly.py"
    text = path.read_text(encoding="utf-8")
    assert "from runtime.boot.boot_decision_core import build_decision_core" in text
    assert "build_decision_core(" in text
