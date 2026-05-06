from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_recovery_surfaces_use_only_outcome_persistence_owner_for_terminal_finalization() -> None:
    recovery = _read("runtime/recovery.py")
    recovery_owner = _read("runtime/execution/executor_recovery.py")
    persistence = _read("runtime/execution/outcome_persistence_lock.py")

    assert "finalize_terminal_recovery_outcome(" in recovery
    assert "mark_delivered(" not in recovery
    assert "finalize_recovered_outcome(" in recovery_owner
    assert "mark_delivered(" not in recovery_owner
    assert "def finalize_terminal_recovery_outcome(" in persistence
