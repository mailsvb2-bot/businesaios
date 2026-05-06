from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_runtime_guard_helpers_contract_exists() -> None:
    p = ROOT / "runtime" / "guard_helpers_contract.py"
    text = p.read_text(encoding="utf-8")
    assert "RUNTIME_GUARD_HELPERS_CONTRACT_VERSION" in text
    assert "ActionContractRuntimePort" in text
    assert "EnvelopeVerificationPort" in text
