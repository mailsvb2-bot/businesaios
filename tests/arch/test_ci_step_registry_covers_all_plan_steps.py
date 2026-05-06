from __future__ import annotations

from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.step_registry import handler_for_step


def test_step_registry_covers_all_plan_steps() -> None:
    names: set[str] = set()
    for gate in ("doctor", "fast", "full", "release", "pre-push", "pre-release"):
        plan = plan_for_gate(gate)
        for step in plan.steps:
            names.add(step.name)

    unresolved: list[str] = []
    for name in sorted(names):
        try:
            handler_for_step(name)
        except KeyError:
            unresolved.append(name)

    assert not unresolved, f"plan steps missing in step registry: {unresolved}"
