from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_guard_contract_exists() -> None:
    p = ROOT / "runtime" / "guard_contract.py"
    text = p.read_text(encoding="utf-8")
    assert "RuntimeGuardPort" in text
    assert "RUNTIME_GUARD_CONTRACT_VERSION" in text
