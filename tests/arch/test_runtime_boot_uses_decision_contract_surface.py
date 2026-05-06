from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_boot_self_check_avoids_concrete_decisioncore_import() -> None:
    path = ROOT / "runtime" / "boot" / "self_check.py"
    text = path.read_text(encoding="utf-8")
    assert "from core.ai.decision_core import DecisionCore" not in text
    assert "core.decision_core" in text


def test_runtime_boot_has_decision_contract_surface() -> None:
    path = ROOT / "runtime" / "boot" / "decision_core_contract.py"
    text = path.read_text(encoding="utf-8")
    assert "class RuntimeDecisionCorePort" in text
    assert "RUNTIME_DECISION_CORE_CONTRACT_VERSION" in text


def test_runtime_boot_self_check_uses_public_decisioncore_surface() -> None:
    path = ROOT / "runtime" / "boot" / "self_check.py"
    text = path.read_text(encoding="utf-8")
    assert "core.decision_core" in text
    assert "core.ai.decision_core" not in text
