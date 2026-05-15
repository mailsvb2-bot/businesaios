from __future__ import annotations

from scripts.ci.contracts import ExecutionPlan, StepDefinition


def _plan(gate: str, *steps: str) -> ExecutionPlan:
    return ExecutionPlan(gate=gate, steps=tuple(StepDefinition(name=s) for s in steps))


def plan_for_gate(gate: str) -> ExecutionPlan:
    if gate == "doctor":
        return _plan("doctor", "assert-project-shape", "dependency-lock", "doctor-check")

    if gate == "fast":
        return _plan(
            "fast",
            "assert-project-shape",
            "dependency-lock",
            "doctor-check",
            "import-smoke",
            "quality-check",
            "architecture-bypass-scan",
            "async-test-contract",
            "lock-tests",
        )

    if gate == "full":
        return _plan(
            "full",
            "assert-project-shape",
            "dependency-lock",
            "doctor-check",
            "import-smoke",
            "demo-e2e-smoke",
            "quality-check",
            "canon-audit",
            "architecture-bypass-scan",
            "async-test-contract",
            "lock-tests",
            "unit-tests",
            "integration-tests",
        )

    if gate == "release":
        return _plan(
            "release",
            "assert-project-shape",
            "dependency-lock",
            "doctor-check",
            "import-smoke",
            "demo-e2e-smoke",
            "quality-check",
            "canon-audit",
            "architecture-bypass-scan",
            "async-test-contract",
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
            "dependency-lock",
            "doctor-check",
            "import-smoke",
            "quality-check",
            "architecture-bypass-scan",
            "async-test-contract",
            "lock-tests",
        )

    if gate == "pre-release":
        return _plan(
            "pre-release",
            "assert-project-shape",
            "dependency-lock",
            "doctor-check",
            "import-smoke",
            "demo-e2e-smoke",
            "quality-check",
            "canon-audit",
            "architecture-bypass-scan",
            "async-test-contract",
            "lock-tests",
            "unit-tests",
            "integration-tests",
            "verify-release",
        )

    raise ValueError(f"unknown gate: {gate}")
