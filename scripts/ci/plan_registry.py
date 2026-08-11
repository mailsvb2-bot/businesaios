from __future__ import annotations

from scripts.ci.contracts import ExecutionPlan, StepDefinition


def _plan(gate: str, *steps: str) -> ExecutionPlan:
    return ExecutionPlan(gate=gate, steps=tuple(StepDefinition(name=s) for s in steps))


def _sid(*parts: str) -> str: return "-".join(parts)
def _pg_migrations_step() -> str: return _sid("postgres", "migrations")
def _pg_live_step() -> str: return _sid("postgres", "live")
def _container_runtime_step() -> str: return _sid("container", "runtime")
def _staging_runtime_step() -> str: return _sid("staging", "runtime")
def _production_boot_step() -> str: return _sid("production", "boot")
def _integrity_auditor_step() -> str: return _sid("integrity", "auditor")
def _user_scenario_gate_step() -> str: return _sid("user", "scenario", "gate")
def _browser_e2e_step() -> str: return _sid("browser", "e2e")


def _release_proof_steps() -> tuple[str, ...]:
    return (
        "postgres-contract", _pg_migrations_step(), _pg_live_step(), _container_runtime_step(),
        _staging_runtime_step(), _production_boot_step(),
    )


def requires_release_proof_environment(*, gate: str, step_name: str) -> bool:
    return gate in {"release", "pre-release"} and step_name in _release_proof_steps()


def requires_release_runtime_environment(*, gate: str, step_name: str) -> bool:
    return gate in {"release", "pre-release"} and step_name in (*_release_proof_steps(), _browser_e2e_step())


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
_LOCKED_BODIES = {
    "fast": _FAST_BODY, "pre-push": _FAST_BODY, "full": (*_FULL_SHARED, "rust-safety-core"),
    "acceptance": (_user_scenario_gate_step(),), "browser": (_browser_e2e_step(),),
    "business-critical": _BUSINESS_CRITICAL_BODY, "targeted-domain": ("targeted-domain-tests",),
    "integrity": (_integrity_auditor_step(),), "integrity-cargo": ("integrity-cargo-tests",),
    "test-quality": ("test-quality",), "test-collection": ("test-quality", "test-collection"),
    "all-tests": ("test-quality", "test-collection", "all-tests"), "coverage": ("code-coverage",),
    "release": (*_RELEASE_SHARED, "build-artifact"), "pre-release": _RELEASE_SHARED,
}
_SHAPE_BODIES = {
    "doctor": (), "rust-safety": ("rust-safety-core",), "rust-deps": ("rust-supply-chain",),
    "postgres-contract": ("postgres-contract",), _pg_migrations_step(): (_pg_migrations_step(),),
    _pg_live_step(): (_pg_live_step(),), _container_runtime_step(): (_container_runtime_step(),),
    _staging_runtime_step(): (_staging_runtime_step(),),
    _production_boot_step(): (
        "postgres-contract", _pg_migrations_step(), _pg_live_step(), _container_runtime_step(), _production_boot_step(),
    ),
}


def plan_for_gate(gate: str) -> ExecutionPlan:
    if gate in _LOCKED_BODIES:
        return _locked(gate, *_LOCKED_BODIES[gate])
    if gate in _SHAPE_BODIES:
        return _shape_doctor(gate, *_SHAPE_BODIES[gate])
    raise ValueError(f"unknown gate: {gate}")
