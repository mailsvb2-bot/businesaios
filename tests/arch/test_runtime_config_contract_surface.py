from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_runtime_config_contract_exists():
    p = ROOT / "runtime" / "config_contract.py"
    text = p.read_text(encoding="utf-8")
    assert "RuntimeConfigPort" in text
    assert "RUNTIME_CONFIG_CONTRACT_VERSION" in text
