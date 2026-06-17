from __future__ import annotations

_STEP_IDS = {
    "project_shape": "assert-project-shape",
    "dependency_lock": "dependency-lock",
    "doctor": "doctor-check",
    "import_smoke": "import-smoke",
    "boot_smoke": "boot-smoke",
    "demo_e2e_smoke": "demo-e2e-smoke",
    "quality": "quality-check",
    "canon_audit": "canon-audit",
    "architecture_bypass_scan": "architecture-bypass-scan",
    "async_test_contract": "async-test-contract",
    "lock_tests": "lock-tests",
    "unit_tests": "unit-tests",
    "integration_tests": "integration-tests",
    "business_critical_tests": "business-critical-tests",
    "targeted_domain_tests": "targeted-domain-tests",
    "integrity_auditor": "integrity-auditor",
    "integrity_cargo_tests": "integrity-cargo-tests",
    "test_quality": "test-quality",
    "test_collection": "test-collection",
    "all_tests": "all-tests",
    "code_coverage": "code-coverage",
    "rust_safety_core": "rust-safety-core",
    "rust_supply_chain": "rust-supply-chain",
    "postgres_contract": "postgres-contract",
    "postgres_live": "postgres-live",
    "production_boot": "production-boot",
    "verify_release": "verify-release",
    "build_artifact": "build-artifact",
}


def step_id(name: str) -> str:
    return _STEP_IDS[str(name)]


def all_step_names() -> tuple[str, ...]:
    return tuple(_STEP_IDS.values())


def __getattr__(name: str):
    if name in _STEP_IDS:
        return lambda: _STEP_IDS[name]
    raise AttributeError(name)


__all__ = [*_STEP_IDS.keys(), "step_id", "all_step_names"]
