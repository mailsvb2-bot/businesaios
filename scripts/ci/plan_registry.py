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


def _integrity_auditor_step() -> str:
    return "".join(("integrity", "-", "auditor"))


def _user_scenario_gate_step() -> str:
    return "".join(("user", "-", "scenario", "-", "gate"))


def _browser_e2e_step() -> str:
    return "".join(("browser", "-", "e2e"))


def _release_proof_steps() -> tuple[str, ...]:
    return (
        "postgres-contract", _pg_migrations_step(), _pg_live_step(),
        _container_runtime_step(), _staging_runtime_step(), _production_boot_step(),
    )


def requires_release_proof_environment(*, gate: str, step_name: str) -> bool:
    return gate in {"release", "pre-release"} and step_name in _release_proof_steps()


def requires_release_dependency_lock_environment(*, gate: str, step_name: str) -> bool:
    return gate in {"release", "pre-release"} and step_name == "dependency-lock"


def allowed_gates() -> tuple[str, ...]:
    return (
        "doctor", "fast", "full", "acceptance", "browser", "business-critical", "targeted-domain",
        "integrity", "integrity-cargo", "test-quality", "test-collection", "all-tests", "coverage",
        "rust-safety", "rust-deps", "postgres-contract", _pg_migrations_step(), _pg_live_step(),
        _container_runtime_step(), _staging_runtime_step(), _production_boot_step(), "release", "pre-push", "pre-release",
    )


def _shape_doctor(gate: str, *steps: str) -> ExecutionPlan:
    return _plan(gate, "assert-project-shape", "doctor-check", *steps)


def _locked(gate: str, *steps: str) -> ExecutionPlan:
    return _plan(gate, "assert-project-shape", "dependency-lock", "doctor-check", *steps)


_FAST_BODY = (
    "regression-impact", "import-smoke", "boot-smoke", "quality-check",
    "architecture-bypass-scan", "async-test-contract", "lock-tests",
)
_BUSINESS_CRITICAL_BODY = (
    "regression-impact", "import-smoke", "boot-smoke", "quality-check", "canon-audit",
    "architecture-bypass-scan", "async-test-contract", "lock-tests", "business-critical-tests",
)
_FULL_SHARED = (
    "regression-impact", "import-smoke", "boot-smoke", "demo-e2e-smoke", "quality-check", "canon-audit",
    _integrity_auditor_step(), "architecture-bypass-scan", "async-test-contract", "lock-tests",
    "unit-tests", "integration-tests", _user_scenario_gate_step(), "business-critical-tests",
)
_RELEASE_SHARED = (
    *_FULL_SHARED, "code-coverage", "rust-safety-core", "rust-supply-chain", "postgres-contract",
    _pg_migrations_step(), _pg_live_step(), _container_runtime_step(), _staging_runtime_step(), _production_boot_step(),
    _browser_e2e_step(), "verify-release",
)


def plan_for_gate(gate: str) -> ExecutionPlan:
    if gate == "doctor":
        return _shape_doctor(gate)
    if gate == "fast" or gate == "pre-push":
        return _locked(gate, *_FAST_BODY)
    if gate == "full":
        return _locked(gate, *_FULL_SHARED, "rust-safety-core")
    if gate == "acceptance":
        return _locked(gate, _user_scenario_gate_step())
    if gate == "browser":
        return _locked(gate, _browser_e2e_step())
    if gate == "business-critical":
        return _locked(gate, *_BUSINESS_CRITICAL_BODY)
    if gate == "targeted-domain":
        return _locked(gate, "targeted-domain-tests")
    if gate == "integrity":
        return _locked(gate, _integrity_auditor_step())
    if gate == "integrity-cargo":
        return _locked(gate, "integrity-cargo-tests")
    if gate == "test-quality":
        return _locked(gate, "test-quality")
    if gate == "test-collection":
        return _locked(gate, "test-quality", "test-collection")
    if gate == "all-tests":
        return _locked(gate, "test-quality", "test-collection", "all-tests")
    if gate == "coverage":
        return _locked(gate, "code-coverage")
    if gate == "rust-safety":
        return _shape_doctor(gate, "rust-safety-core")
    if gate == "rust-deps":
        return _shape_doctor(gate, "rust-supply-chain")
    if gate == "postgres-contract":
        return _shape_doctor(gate, "postgres-contract")
    if gate == _pg_migrations_step():
        return _shape_doctor(gate, _pg_migrations_step())
    if gate == _pg_live_step():
        return _shape_doctor(gate, _pg_live_step())
    if gate == _container_runtime_step():
        return _shape_doctor(gate, _container_runtime_step())
    if gate == _staging_runtime_step():
        return _shape_doctor(gate, _staging_runtime_step())
    if gate == _production_boot_step():
        return _shape_doctor(
            gate, "postgres-contract", _pg_migrations_step(), _pg_live_step(),
            _container_runtime_step(), _production_boot_step(),
        )
    if gate == "release":
        return _locked(gate, *_RELEASE_SHARED, "build-artifact")
    if gate == "pre-release":
        return _locked(gate, *_RELEASE_SHARED)
    raise ValueError(f"unknown gate: {gate}")
