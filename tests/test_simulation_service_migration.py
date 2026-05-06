from __future__ import annotations

from core.simulation.contracts import SimScore
from core.simulation.service import score_step


def test_score_step_remains_available_via_canon_service() -> None:
    item = score_step(action="request_plan", payload={"uplift": 1.0}, snapshot={"x": 1})
    assert isinstance(item, SimScore)
    assert item.confidence >= 0.2
