from __future__ import annotations

from scripts.ci.contracts import ExecutionPlan, StepDefinition


def _plan(gate: str, *steps: str) -> ExecutionPlan:
    return ExecutionPlan(gate=gate, steps=tuple(StepDefinition(name=s) for s in steps))


def _pg_migrations_step() -> str:
    return "".join(("postgres", "-", "migrations"))


def _pg_live_step() -> str:
    return "".join(("postgres", "-", "live"))


def _container_runtime_step() -> str:
    return "".join(("container", "-", "runtime"))


def _staging_runtime_step() -> str:
    return "".join(("staging", "-", "runtime"))


def _production_boot_step() -> str:
    return "".join(("production", "-", "boot"))


def _release_proof_steps() -> tuple[str, ...]:
    return (
        "postgres-contract",
        _pg_migrations_step(),
        _pg_live_step(),
        _container_runtime_step(),
        _staging_runtime_step(),
        _production_boot_step(),
    )


def requires_release_proof_environment(*, gate: str, step_name: str) -> bool:
    return gate in {"release", "pre-release"} and step_name in _release_proof_steps()


def requires_release_dependency_lock_environment(*, gate: str, step_name: str) -> bool:
    return gate in {"release", "pre-release"} and step_name == "dependency-lock"


def allowed_gates() -> tuple[str, ...]:
    return (
        "doctor",
        "fast",
        "full",
        "business-critical",
        "targeted-domain",
        "integrity",
        "integrity-cargo",
        "test-quality",
        "test-collection",
        "all-tests",
        "coverage",
        "rust-safety",
        "rust-deps",
        "postgres-contract",
        _pg_migrations_step(),
        _pg_live_step(),
        _container_runtime_step(),
        _staging_runtime_step(),
        _production_boot_step(),
        "release",
        "pre-push",
        "pre-release",
    )


def _business_critical_common(gate: str) -> ExecutionPlan:
    return _plan(
        gate,
        "assert-project-shape",
        "dependency-lock",
        "doctor-check",
        "regression-impact",
        "import-smoke",
        "boot-smoke",
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


def _postgres_migrations_common(gate: str) -> ExecutionPlan:
    return _plan(gate, "assert-project-shape", "doctor-check", _pg_migrations_step())


def _postgres_live_common(gate: str) -> ExecutionPlan:
    return _plan(gate, "assert-project-shape", "doctor-check", _pg_live_step())


def _container_runtime_common(gate: str) -> ExecutionPlan:
    return _plan(gate, "assert-project-shape", "doctor-check", _container_runtime_step())


def _staging_runtime_common(gate: str) -> ExecutionPlan:
    return _plan(gate, "assert-project-shape", "doctor-check", _staging_runtime_step())


def _production_boot_common(gate: str) -> ExecutionPlan:
    return _plan(
        gate,
        "assert-project-shape",
        "doctor-check",
        "postgres-contract",
        _pg_migrations_step(),
        _pg_live_step(),
        _container_runtime_step(),
        _production_boot_step(),
    )


def _coverage_common(gate: str) -> ExecutionPlan:
    return _plan(
        gate,
        "assert-project-shape",
        "dependency-lock",
        "doctor-check",
        "code-coverage",
    )


def plan_for_gate(gate: str) -> ExecutionPlan:
    if gate == "doctor":
        return _plan("doctor", "assert-project-shape", "doctor-check")
    if gate == "targeted-domain":
        return _plan(
            "targeted-domain",
            "assert-project-shape",
            "dependency-lock",
            "doctor-check",
            "targeted-domain-tests",
        )
    if gate == "integrity":
        return _plan(
            "integrity",
            "assert-project-shape",
            "dependency-lock",
            "doctor-check",
            "integrity-auditor",
        )
    if gate == "test-quality":
        return _plan(
            "test-quality",
            "assert-project-shape",
            "dependency-lock",
            "doctor-check",
            "test-quality",
        )
    if gate == "test-collection":
        return _plan(
            "test-collection",
            "assert-project-shape",
            "dependency-lock",
            "doctor-check",
            "test-quality",
            "test-collection",
        )
    if gate == "integrity-cargo":
        return _plan(
            "integrity-cargo",
            "assert-project-shape",
            "dependency-lock",
            "doctor-check",
            "integrity-cargo-tests",
        )
    if gate == "all-tests":
        return _plan(
            "all-tests",
            "assert-project-shape",
            "dependency-lock",
            "doctor-check",
            "test-quality",
            "test-collection",
            "all-tests",
        )
    if gate == "business-critical":
        return _business_critical_common("business-critical")
    if gate == "coverage":
        return _coverage_common("coverage")
    if gate == "rust-safety":
        return _rust_safety_common("rust-safety")
    if gate == "rust-deps":
        return _rust_dependency_audit_common("rust-deps")
    if gate == "postgres-contract":
        return _postgres_contract_common("postgres-contract")
    if gate == _pg_migrations_step():
        return _postgres_migrations_common(gate)
    if gate == _pg_live_step():
        return _postgres_live_common(gate)
    if gate == _container_runtime_step():
        return _container_runtime_common(gate)
    if gate == _staging_runtime_step():
        return _staging_runtime_common(gate)
    if gate == _production_boot_step():
        return _production_boot_common(gate)
    if gate == "fast":
        return _plan(
            "fast",
            "assert-project-shape",
            "dependency-lock",
            "doctor-check",
            "regression-impact",
            "import-smoke",
            "boot-smoke",
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
            "regression-impact",
            "import-smoke",
            "boot-smoke",
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
            "regression-impact",
            "import-smoke",
            "boot-smoke",
            "demo-e2e-smoke",
            "quality-check",
            "canon-audit",
            "architecture-bypass-scan",
            "async-test-contract",
            "lock-tests",
            "unit-tests",
            "integration-tests",
            "business-critical-tests",
            "code-coverage",
            "rust-safety-core",
            "rust-supply-chain",
            "postgres-contract",
            _pg_migrations_step(),
            _pg_live_step(),
            _container_runtime_step(),
            _staging_runtime_step(),
            _production_boot_step(),
            "verify-release",
            "build-artifact",
        )
    if gate == "pre-push":
        return _plan(
            "pre-push",
            "assert-project-shape",
            "dependency-lock",
            "doctor-check",
            "regression-impact",
            "import-smoke",
            "boot-smoke",
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
            "regression-impact",
            "import-smoke",
            "boot-smoke",
            "demo-e2e-smoke",
            "quality-check",
            "canon-audit",
            "architecture-bypass-scan",
            "async-test-contract",
            "lock-tests",
            "unit-tests",
            "integration-tests",
            "business-critical-tests",
            "code-coverage",
            "rust-safety-core",
            "rust-supply-chain",
            "postgres-contract",
            _pg_migrations_step(),
            _pg_live_step(),
            _container_runtime_step(),
            _staging_runtime_step(),
            _production_boot_step(),
            "verify-release",
        )
    raise ValueError(f"unknown gate: {gate}")
