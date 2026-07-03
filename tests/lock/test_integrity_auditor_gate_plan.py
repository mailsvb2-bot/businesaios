from __future__ import annotations

from scripts.ci.plan_registry import plan_for_gate


def test_integrity_auditor_is_required_for_long_gates() -> None:
    for gate in ("full", "release", "pre-release"):
        steps = [step.name for step in plan_for_gate(gate).steps]
        assert "integrity-auditor" in steps


def test_integrity_auditor_does_not_expand_fast_gate() -> None:
    steps = [step.name for step in plan_for_gate("fast").steps]
    assert "integrity-auditor" not in steps
