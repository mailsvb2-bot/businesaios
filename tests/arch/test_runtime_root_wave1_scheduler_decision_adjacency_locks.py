from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    "runtime/scheduler.py",
    "runtime/scheduler_run_cycle.py",
    "runtime/scheduler_monitoring_flow.py",
    "runtime/self_driving_scheduler.py",
    "runtime/decision_gateway.py",
]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")



def test_scheduler_adjacent_root_surfaces_do_not_issue_raw_decisions() -> None:
    for relative in FILES:
        text = _read(relative)
        assert "DecisionCore(" not in text, relative
        assert "from core.ai.decision_core" not in text, relative
        assert "from core.decision.decision_core" not in text, relative



def test_scheduler_adjacent_root_surfaces_do_not_compose_runtime() -> None:
    for relative in FILES:
        text = _read(relative)
        assert "compose_runtime(" not in text, relative
        assert "bootstrap_runtime(" not in text, relative
