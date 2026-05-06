from __future__ import annotations

from scripts.ci.plan_registry import plan_for_gate


def _names(gate: str) -> list[str]:
    return [step.name for step in plan_for_gate(gate).steps]


def test_gate_order_is_canonical() -> None:
    assert _names("doctor") == [
        "assert-project-shape",
        "doctor-check",
    ]
    assert _names("fast") == [
        "assert-project-shape",
        "doctor-check",
        "import-smoke",
        "quality-check",
        "lock-tests",
    ]
    assert _names("full") == [
        "assert-project-shape",
        "doctor-check",
        "import-smoke",
        "quality-check",
        "canon-audit",
        "lock-tests",
        "unit-tests",
        "integration-tests",
    ]
    assert _names("release") == [
        "assert-project-shape",
        "doctor-check",
        "import-smoke",
        "quality-check",
        "canon-audit",
        "lock-tests",
        "unit-tests",
        "integration-tests",
        "verify-release",
        "build-artifact",
    ]
