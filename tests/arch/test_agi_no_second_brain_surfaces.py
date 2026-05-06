from __future__ import annotations

from pathlib import Path


FORBIDDEN_SURFACES = (
    "core/ai/agi_decision_core.py",
    "core/decision/agi_decision_core.py",
    "execution/agi_executor.py",
    "execution/agi_action_selector.py",
    "execution/secondary_decision_loop.py",
    "learning/autonomous_brain.py",
    "bootstrap/secondary_decision_world_model.py",
    "bootstrap/agi_decision_core_adapter.py",
    "bootstrap/parallel_decision_adapter.py",
)


def test_no_second_brain_surfaces_are_added():
    for rel in FORBIDDEN_SURFACES:
        assert not Path(rel).exists(), f"forbidden second-brain surface exists: {rel}"
