from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_messaging_router_has_no_decisioncore_language() -> None:
    path = ROOT / "runtime" / "messaging" / "router.py"
    text = path.read_text(encoding="utf-8")
    assert "DecisionCore" not in text
    assert "policy selection" in text  # present only as non-responsibility text


def test_runtime_messaging_router_contract_exists() -> None:
    path = ROOT / "runtime" / "messaging" / "router_contract.py"
    text = path.read_text(encoding="utf-8")
    assert "ConversationRoute" in text
    assert "RUNTIME_MESSAGING_ROUTER_CONTRACT_VERSION" in text
