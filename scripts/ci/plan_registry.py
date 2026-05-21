from __future__ import annotations

from scripts.ci.contracts import ExecutionPlan, StepDefinition


def _plan(gate: str, *steps: str) -> ExecutionPlan:
    return ExecutionPlan(gate=gate, steps=tuple(StepDefinition(name=s) for s in steps))


def _business_critical_common(gate: str) -> ExecutionPlan:
    return _plan(
        gate,
        "assert-project-shape",
        "dependency-lock",
        "doctor-check",
        "import-smoke",
        "quality-check",
        "canon-audit",
        "architecture-bypass-scan",
        "async-test-contract",
        "lock-tests",
        "business-critical-tests",
    )


def _rust_safety_common(gate: str) -> ExecutionPlan:
    return _plan(gate, "assert-project-shape", "doctor-check", "rust-safety-core")


def _rust_dependency_audit_common(gate: str) -> ExecutionPlan:
    return _plan(gate, "assert-project-shape", "doctor-check", "rust-supply-chain")


def _postgres_contract_common(gate: str) -> ExecutionPlan:
    return _plan(gate, "assert-project-shape", "doctor-check", "postgres-contract")


def _postgres_live_common(gate: str) -> ExecutionPlan:
    return _plan(gate, "assert-project-shape", "doctor-check", "postgres-live")


def _production_boot_common(gate: str) -> ExecutionPlan:
    return _plan(gate, "assert-project-shape", "doctor-check", "postgres-contract", "postgres-live", "production-boot")


def plan_for_gate(gate: str) -> ExecutionPlan:
    if gate == "doctor":
        return _plan("doctor", "assert-project-shape", "dependency-lock", "doctor-check")
    if gate == "business-critical":
        return _business_critical_common("business-critical")
    if gate == "rust-safety":
        return _rust_safety_common("rust-safety")
    if gate == "rust-deps":
        return _rust_dependency_audit_common("rust-deps")
    if gate == "postgres-contract":
        return _postgres_contract_common("postgres-contract")
    if gate == "postgres-live":
        return _postgres_live_common("postgres-live")
    if gate == "production-boot":
        return _production_boot_common("production-boot")
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
            "business-critical-tests",
            "rust-safety-core",
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
            "business-critical-tests",
            "rust-safety-core",
            "rust-supply-chain",
            "postgres-contract",
            "postgres-live",
            "production-boot",
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
            "business-critical-tests",
            "rust-safety-core",
            "rust-supply-chain",
            "postgres-contract",
            "postgres-live",
            "production-boot",
            "verify-release",
        )
    raise ValueError(f"unknown gate: {gate}")