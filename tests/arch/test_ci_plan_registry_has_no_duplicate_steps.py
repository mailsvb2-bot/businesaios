from __future__ import annotations

from scripts.ci.plan_registry import plan_for_gate


def test_each_gate_has_unique_step_names() -> None:
    for gate in ("doctor", "fast", "full", "release", "pre-push", "pre-release"):
        plan = plan_for_gate(gate)
        names = [step.name for step in plan.steps]
        assert len(names) == len(set(names)), f"duplicate steps in gate={gate}: {names}"
