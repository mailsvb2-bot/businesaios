from __future__ import annotations

from collections.abc import Callable
from importlib import import_module

from scripts.ci import step_ids as _step_ids

StepHandler = Callable[[], tuple[bool, str]]


def project_shape(): return _step_ids.project_shape()
def doctor(): return _step_ids.doctor()
def regression_impact(): return _step_ids.regression_impact()
def baseline_contract(): return _step_ids.baseline_contract()
def quality(): return _step_ids.quality()
def canon_audit(): return _step_ids.canon_audit()
def lock_tests(): return _step_ids.lock_tests()
def unit_tests(): return _step_ids.unit_tests()
def integration_tests(): return _step_ids.integration_tests()
def verify_release(): return _step_ids.verify_release()
def build_artifact(): return _step_ids.build_artifact()


def _lazy_handler(module_name: str, attr_name: str = "run") -> StepHandler:
    """Return a dependency-light step handler.

    The CI CLI must be able to import the registry and run preflight/dependency
    gates even when optional test/runtime dependencies are missing from the host.
    Heavy step modules are imported only when their step is actually executed.
    """

    def _run() -> tuple[bool, str]:
        module = import_module(module_name)
        handler = getattr(module, attr_name)
        return handler()

    _run.__name__ = f"lazy_{module_name.rpartition('.')[2]}_{attr_name}"
    return _run


run_doctor = _lazy_handler("scripts.ci.doctor", "run_doctor")


_REGISTRY: dict[str, StepHandler] = {
    project_shape(): _lazy_handler("scripts.ci.step_project_shape"),
    _step_ids.dependency_lock(): _lazy_handler("scripts.ci.step_dependency_lock"),
    doctor(): run_doctor,
    regression_impact(): _lazy_handler("scripts.ci.step_regression_impact"),
    baseline_contract(): _lazy_handler("scripts.ci.step_baseline_contract"),
    _step_ids.import_smoke(): _lazy_handler("scripts.ci.step_import_smoke"),
    _step_ids.boot_smoke(): _lazy_handler("scripts.ci.step_boot_smoke"),
    _step_ids.demo_e2e_smoke(): _lazy_handler("scripts.ci.step_demo_e2e_smoke"),
    quality(): _lazy_handler("scripts.ci.step_quality"),
    canon_audit(): _lazy_handler("scripts.ci.step_canon_audit"),
    _step_ids.architecture_bypass_scan(): _lazy_handler("scripts.ci.step_architecture_bypass_scan"),
    _step_ids.async_test_contract(): _lazy_handler("scripts.ci.step_async_test_contract"),
    lock_tests(): _lazy_handler("scripts.ci.step_lock_tests"),
    unit_tests(): _lazy_handler("scripts.ci.step_unit_tests"),
    integration_tests(): _lazy_handler("scripts.ci.step_integration_tests"),
    _step_ids.business_critical_tests(): _lazy_handler("scripts.ci.step_business_critical_tests"),
    _step_ids.targeted_domain_tests(): _lazy_handler("scripts.ci.step_targeted_domain_tests"),
    _step_ids.integrity_auditor(): _lazy_handler("scripts.ci.step_integrity_auditor"),
    _step_ids.integrity_cargo_tests(): _lazy_handler("scripts.ci.step_integrity_cargo_tests"),
    _step_ids.test_quality(): _lazy_handler("scripts.ci.step_test_quality"),
    _step_ids.test_collection(): _lazy_handler("scripts.ci.step_test_collection"),
    _step_ids.all_tests(): _lazy_handler("scripts.ci.step_all_tests"),
    _step_ids.code_coverage(): _lazy_handler("scripts.ci.step_code_coverage"),
    _step_ids.rust_safety_core(): _lazy_handler("scripts.ci.step_rust_safety_core"),
    _step_ids.rust_supply_chain(): _lazy_handler("scripts.ci.step_rust_supply_chain"),
    _step_ids.postgres_contract(): _lazy_handler("scripts.ci.step_postgres_contract"),
    _step_ids.postgres_migrations(): _lazy_handler("scripts.ci.step_postgres_migrations"),
    _step_ids.postgres_live(): _lazy_handler("scripts.ci.step_postgres_live"),
    _step_ids.container_runtime(): _lazy_handler("scripts.ci.step_container_runtime"),
    _step_ids.staging_runtime(): _lazy_handler("scripts.ci.step_staging_runtime"),
    _step_ids.production_boot(): _lazy_handler("scripts.ci.step_production_boot"),
    verify_release(): _lazy_handler("scripts.ci.step_verify_release"),
    build_artifact(): _lazy_handler("scripts.ci.step_build_artifact"),
}


def handler_for_step(name: str) -> StepHandler:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"unknown step: {name}") from exc


def registered_step_names() -> tuple[str, ...]:
    return tuple(_REGISTRY)


def all_step_names() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY.keys()))
