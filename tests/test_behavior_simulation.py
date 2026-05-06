from __future__ import annotations

from core.behavior.math.complex4 import Complex4
from core.behavior.simulation.what_if_plan import WhatIfPlan
from core.behavior.simulation.what_if_runner import run_what_if_plan


def test_run_what_if_plan_returns_observables() -> None:
    result = run_what_if_plan(
        Complex4((0.4, 0.4, 0.4, 0.3), (0.0, 0.0, 0.0, 0.0)),
        WhatIfPlan(plan_id="p1", operator_keys=("message_open", "content_engage")),
    )
    assert result["plan_id"] == "p1"
    assert "coherence_score" in result["observables"]
