from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_tla_runtime_decision_gate_assets_exist() -> None:
    spec = ROOT / "formal" / "tla" / "runtime_decision_gate.tla"
    cfg = ROOT / "formal" / "tla" / "runtime_decision_gate.cfg"
    assert spec.exists()
    assert cfg.exists()

    text = spec.read_text(encoding="utf-8")
    assert "NoBypass" in text
    assert "FailClosed" in text
    assert "ObservabilityComplete" in text
