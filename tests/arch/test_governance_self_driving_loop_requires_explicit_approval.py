from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_governance_self_driving_loop_uses_explicit_approval_check() -> None:
    path = ROOT / "governance" / "self_driving_loop.py"
    text = path.read_text(encoding="utf-8")
    assert "approved = bool(self._rollout.approve(old_metrics, new_metrics))" in text
    assert "if not approved:" in text
    assert "self._registry.swap(new_policy)" in text


def test_governance_self_driving_contract_surface_exists() -> None:
    path = ROOT / "governance" / "self_driving_contract.py"
    text = path.read_text(encoding="utf-8")
    assert "class GovernedEvolutionPort" in text
    assert "SELF_DRIVING_GOVERNANCE_CONTRACT_VERSION" in text
