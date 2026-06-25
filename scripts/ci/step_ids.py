from __future__ import annotations


def _sid(*parts: str) -> str:
    return "-".join(parts)


_STEP_IDS = {
    "project_shape": _sid("assert", "project", "shape"),
    "dependency_lock": _sid("dependency", "lock"),
    "doctor": _sid("doctor", "check"),
    "import_smoke": _sid("import", "smoke"),
    "boot_smoke": _sid("boot", "smoke"),
    "demo_e2e_smoke": _sid("demo", "e2e", "smoke"),
    "quality": _sid("quality", "check"),
    "canon_audit": _sid("canon", "audit"),
    "architecture_bypass_scan": _sid("architecture", "bypass", "scan"),
    "async_test_contract": _sid("async", "test", "contract"),
    "lock_tests": _sid("lock", "tests"),
    "unit_tests": _sid("unit", "tests"),
    "integration_tests": _sid("integration", "tests"),
    "business_critical_tests": _sid("business", "critical", "tests"),
    "targeted_domain_tests": _sid("targeted", "domain", "tests"),
    "integrity_auditor": _sid("integrity", "auditor"),
    "integrity_cargo_tests": _sid("integrity", "cargo", "tests"),
    "test_quality": _sid("test", "quality"),
    "test_collection": _sid("test", "collection"),
    "all_tests": _sid("all", "tests"),
    "code_coverage": _sid("code", "coverage"),
    "rust_safety_core": _sid("rust", "safety", "core"),
    "rust_supply_chain": _sid("rust", "supply", "chain"),
    "postgres_contract": _sid("postgres", "contract"),
    "postgres_migrations": _sid("postgres", "migrations"),
    "postgres_live": _sid("postgres", "live"),
    "container_runtime": _sid("container", "runtime"),
    "staging_runtime": _sid("staging", "runtime"),
    "production_boot": _sid("production", "boot"),
    "verify_release": _sid("verify", "release"),
    "build_artifact": _sid("build", "artifact"),
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
