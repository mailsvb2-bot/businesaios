from __future__ import annotations

from scripts.ci.contracts import ExecutionPlan, StepDefinition


def _plan(gate: str, *steps: str) -> ExecutionPlan:
    return ExecutionPlan(gate=gate, steps=tuple(StepDefinition(name=s) for s in steps))


def plan_for_gate(gate: str) -> ExecutionPlan:
    if gate == "doctor":
        # Doctor must stay lightweight: filesystem shape + deterministic health checks only.
        return _plan("doctor", "assert-project-shape", "doctor-check")

    if gate == "fast":
        # Fast is the required P0 developer gate: boot/import smoke before heavier checks.
        return _plan(
            "fast",
            "assert-project-shape",
            "doctor-check",
            "import-smoke",
            "quality-check",
            "lock-tests",
        )

    if gate == "full":
        return _plan(
            "full",
            "assert-project-shape",
            "doctor-check",
            "import-smoke",
            "quality-check",
            "canon-audit",
            "lock-tests",
            "unit-tests",
            "integration-tests",
        )

    if gate == "release":
        return _plan(
            "release",
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
        )

    if gate == "pre-push":
        return _plan(
            "pre-push",
            "assert-project-shape",
            "doctor-check",
            "import-smoke",
            "quality-check",
            "lock-tests",
        )

    if gate == "pre-release":
        return _plan(
            "pre-release",
            "assert-project-shape",
            "doctor-check",
            "import-smoke",
            "quality-check",
            "canon-audit",
            "lock-tests",
            "unit-tests",
            "integration-tests",
            "verify-release",
        )

    raise ValueError(f"unknown gate: {gate}")
