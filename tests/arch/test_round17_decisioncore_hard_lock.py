from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_decision_sovereignty_doc_exists() -> None:
    path = ROOT / "core" / "decisioning" / "DECISION_SOVEREIGNTY.md"
    text = path.read_text(encoding="utf-8")
    assert "DecisionCore is the single authority" in text


def test_decision_graph_contract_exists() -> None:
    path = ROOT / "core" / "decisioning" / "decision_graph_contract.py"
    text = path.read_text(encoding="utf-8")
    assert "DECISION_GRAPH_CONTRACT_VERSION" in text
    assert "class DecisionGraph" in text


def test_decision_space_invariants_exist() -> None:
    path = ROOT / "core" / "decisioning" / "decision_space_invariants.py"
    text = path.read_text(encoding="utf-8")
    assert "FORBIDDEN_CAPABILITIES_OUTSIDE_CORE" in text
    assert "ALLOWED_ADVISORY_CAPABILITIES" in text
