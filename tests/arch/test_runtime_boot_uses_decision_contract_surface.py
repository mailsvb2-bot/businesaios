from __future__ import annotations

from pathlib import Path

from bootstrap.decision_core_contract import (
    RUNTIME_DECISION_CORE_CONTRACT_VERSION as BOOTSTRAP_CONTRACT_VERSION,
)
from bootstrap.decision_core_contract import RuntimeDecisionCorePort as BootstrapRuntimeDecisionCorePort
from runtime.boot.decision_core_contract import (
    RUNTIME_DECISION_CORE_CONTRACT_VERSION as RUNTIME_CONTRACT_VERSION,
)
from runtime.boot.decision_core_contract import RuntimeDecisionCorePort as RuntimeBootDecisionCorePort

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_boot_self_check_avoids_concrete_decisioncore_import() -> None:
    path = ROOT / "runtime" / "boot" / "self_check.py"
    text = path.read_text(encoding="utf-8")
    assert "from core.ai.decision_core import DecisionCore" not in text
    assert "core.decision_core" in text


def test_runtime_boot_reexports_the_single_decision_contract() -> None:
    path = ROOT / "runtime" / "boot" / "decision_core_contract.py"
    text = path.read_text(encoding="utf-8")
    assert "from bootstrap.decision_core_contract import" in text
    assert "CANON_RUNTIME_DECISION_CORE_CONTRACT_REEXPORT = True" in text
    assert RuntimeBootDecisionCorePort is BootstrapRuntimeDecisionCorePort
    assert RUNTIME_CONTRACT_VERSION == BOOTSTRAP_CONTRACT_VERSION


def test_runtime_boot_self_check_uses_public_decisioncore_surface() -> None:
    path = ROOT / "runtime" / "boot" / "self_check.py"
    text = path.read_text(encoding="utf-8")
    assert "core.decision_core" in text
    assert "core.ai.decision_core" not in text
