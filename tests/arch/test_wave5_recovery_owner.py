from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_recovery_uses_canonical_quarantine_owner() -> None:
    text = (ROOT / "runtime" / "recovery.py").read_text(encoding="utf-8")
    assert "quarantine_recovery_outcome" in text
    assert "move_to_dead_letter(" not in text


def test_recovery_policy_engine_exposes_resolve_semantics() -> None:
    text = (ROOT / "reliability" / "recovery_policy_engine.py").read_text(encoding="utf-8")
    assert "CANON_RECOVERY_POLICY_RESOLVE_ONLY = True" in text
    assert "def resolve(" in text


def test_recovery_policy_engine_does_not_expose_legacy_decide_api() -> None:
    text = (ROOT / "reliability" / "recovery_policy_engine.py").read_text(encoding="utf-8")
    assert "def decide(" not in text
