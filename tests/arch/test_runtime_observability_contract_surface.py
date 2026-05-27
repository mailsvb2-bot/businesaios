from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_runtime_observability_contract_exists():
    p = ROOT / "runtime" / "observability_contract.py"
    text = p.read_text(encoding="utf-8")
    assert "RuntimeAuditPort" in text
    assert "RuntimeMetricsPort" in text
