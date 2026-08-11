from __future__ import annotations

from scripts.ci.contracts import ExecutionPlan, StepDefinition

PG_MIGRATIONS, PG_LIVE, CONTAINER_RUNTIME, STAGING_RUNTIME, PRODUCTION_BOOT = (
    "postgres-migrations", "postgres-live", "container-runtime", "staging-runtime", "production-boot",
)
INTEGRITY, USER_SCENARIOS, BROWSER = "integrity-auditor", "user-scenario-gate", "browser-e2e"
_RELEASE_PROOF = ("postgres-contract", PG_MIGRATIONS, PG_LIVE, CONTAINER_RUNTIME, STAGING_RUNTIME, PRODUCTION_BOOT)
_FAST = ("regression-impact", "import-smoke", "boot-smoke", "quality-check", "architecture-bypass-scan", "async-test-contract", "lock-tests")
_BUSINESS = (*_FAST[:3], "quality-check", "canon-audit", *_FAST[4:], "business-critical-tests")
_FULL = (
    "regression-impact", "import-smoke", "boot-smoke", "demo-e2e-smoke", "quality-check", "canon-audit",
    INTEGRITY, "architecture-bypass-scan", "async-test-contract", "lock-tests", "unit-tests",
    "integration-tests", USER_SCENARIOS, "business-critical-tests",
)
_RELEASE = (*_FULL, "code-coverage", "rust-safety-core", "rust-supply-chain", *_RELEASE_PROOF, BROWSER, "verify-release")
_PLANS = {
    "doctor": (), "fast": _FAST, "full": (*_FULL, "rust-safety-core"), "acceptance": (USER_SCENARIOS,),
    "browser": (BROWSER,), "business-critical": _BUSINESS, "targeted-domain": ("targeted-domain-tests",),
    "integrity": (INTEGRITY,), "integrity-cargo": ("integrity-cargo-tests",), "test-quality": ("test-quality",),
    "test-collection": ("test-quality", "test-collection"), "all-tests": ("test-quality", "test-collection", "all-tests"),
    "coverage": ("code-coverage",), "rust-safety": ("rust-safety-core",), "rust-deps": ("rust-supply-chain",),
    "postgres-contract": ("postgres-contract",), PG_MIGRATIONS: (PG_MIGRATIONS,), PG_LIVE: (PG_LIVE,),
    CONTAINER_RUNTIME: (CONTAINER_RUNTIME,), STAGING_RUNTIME: (STAGING_RUNTIME,),
    PRODUCTION_BOOT: ("postgres-contract", PG_MIGRATIONS, PG_LIVE, CONTAINER_RUNTIME, PRODUCTION_BOOT),
    "release": (*_RELEASE, "build-artifact"), "pre-push": _FAST, "pre-release": _RELEASE,
}
_NO_LOCK = {"doctor", "rust-safety", "rust-deps", "postgres-contract", PG_MIGRATIONS, PG_LIVE, CONTAINER_RUNTIME, STAGING_RUNTIME, PRODUCTION_BOOT}


def requires_release_proof_environment(*, gate: str, step_name: str) -> bool:
    return gate in {"release", "pre-release"} and step_name in _RELEASE_PROOF


def requires_release_runtime_environment(*, gate: str, step_name: str) -> bool:
    return gate in {"release", "pre-release"} and step_name in (*_RELEASE_PROOF, BROWSER)


def requires_release_dependency_lock_environment(*, gate: str, step_name: str) -> bool:
    return gate in {"release", "pre-release"} and step_name == "dependency-lock"


def allowed_gates() -> tuple[str, ...]:
    return tuple(_PLANS)


def plan_for_gate(gate: str) -> ExecutionPlan:
    body = _PLANS.get(gate)
    if body is None:
        raise ValueError(f"unknown gate: {gate}")
    prefix = ("assert-project-shape", "doctor-check") if gate in _NO_LOCK else ("assert-project-shape", "dependency-lock", "doctor-check")
    return ExecutionPlan(gate=gate, steps=tuple(StepDefinition(name=name) for name in (*prefix, *body)))
