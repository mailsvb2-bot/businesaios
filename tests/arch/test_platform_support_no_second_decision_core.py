from __future__ import annotations

from pathlib import Path


def test_platform_support_uses_local_decision_service_name() -> None:
    text = Path("runtime/platform/support/optimization/contracts.py").read_text(encoding="utf-8")
    assert "CANON_COMPAT_SHIM = True" in text
    assert "class DecisionCore" not in text


def test_self_optimization_loop_does_not_import_shadow_decision_core() -> None:
    text = Path("runtime/platform/support/optimization/self_optimization_loop.py").read_text(encoding="utf-8")
    assert "OptimizationDecisionService" in text
    assert "DecisionCore" not in text
    assert "platform/optimization/search" not in text
