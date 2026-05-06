from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_replay_surface_is_thin_and_non_deciding() -> None:
    text = (ROOT / "runtime" / "replay.py").read_text(encoding="utf-8")
    assert "CANON_RUNTIME_REPLAY_THIN_SURFACE = True" in text
    assert "CANON_RUNTIME_REPLAY_NO_DECISION_LOGIC = True" in text
    assert "DecisionEnvelope" in text
