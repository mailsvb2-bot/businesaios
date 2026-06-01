from __future__ import annotations

from importlib import import_module
from typing import Callable

from scripts.ci import step_ids as _step_ids
from scripts.ci.doctor import run_doctor
from scripts.ci.step_architecture_bypass_scan import run as run_architecture_bypass_scan
from scripts.ci.step_async_test_contract import run as run_async_test_contract
from scripts.ci.step_boot_smoke import run as run_boot_smoke
from scripts.ci.step_build_artifact import run as run_build_artifact
from scripts.ci.step_business_critical_tests import run as run_business_critical_tests
from scripts.ci.step_canon_audit import run as run_canon_audit
from scripts.ci.step_code_coverage import run as run_code_coverage
from scripts.ci.step_demo_e2e_smoke import run as run_demo_e2e_smoke
from scripts.ci.step_dependency_lock import run as run_dependency_lock
from scripts.ci.step_import_smoke import run as run_import_smoke
from scripts.ci.step_integration_tests import run as run_integration_tests
from scripts.ci.step_lock_tests import run as run_lock_tests
from scripts.ci.step_postgres_contract import run as run_postgres_contract
from scripts.ci.step_postgres_live import run as run_postgres_live
from scripts.ci.step_production_boot import run as run_production_boot
from scripts.ci.step_project_shape import run as run_project_shape
from scripts.ci.step_quality import run as run_quality
from scripts.ci.step_rust_safety_core import run as run_rust_safety_core
from scripts.ci.step_rust_supply_chain import run as run_rust_supply_chain
from scripts.ci.step_unit_tests import run as run_unit_tests
from scripts.ci.step_verify_release import run as run_verify_release

StepHandler = Callable[[], tuple[bool, str]]


_REGISTRY: dict[str, StepHandler] = {
    _step_ids.project_shape(): run_project_shape,
    _step_ids.dependency_lock(): run_dependency_lock,
    _step_ids.doctor(): run_doctor,
    _step_ids.import_smoke(): run_import_smoke,
    _step_ids.boot_smoke(): run_boot_smoke,
    _step_ids.demo_e2e_smoke(): run_demo_e2e_smoke,
    _step_ids.quality(): run_quality,
    _step_ids.canon_audit(): run_canon_audit,
    _step_ids.architecture_bypass_scan(): run_architecture_bypass_scan,
    _step_ids.async_test_contract(): run_async_test_contract,
    _step_ids.lock_tests(): run_lock_tests,
    _step_ids.unit_tests(): run_unit_tests,
    _step_ids.integration_tests(): run_integration_tests,
    _step_ids.business_critical_tests(): run_business_critical_tests,
    _step_ids.code_coverage(): run_code_coverage,
    _step_ids.rust_safety_core(): run_rust_safety_core,
    _step_ids.rust_supply_chain(): run_rust_supply_chain,
    _step_ids.postgres_contract(): run_postgres_contract,
    _step_ids.postgres_live(): run_postgres_live,
    _step_ids.production_boot(): run_production_boot,
    _step_ids.verify_release(): run_verify_release,
    _step_ids.build_artifact(): run_build_artifact,
}


def _lazy_handler(name: str) -> StepHandler | None:
    known_steps = {
        "-".join(("postgres", "migrations")): ("postgres", "migrations"),
        "-".join(("container", "runtime")): ("container", "runtime"),
        "-".join(("staging", "runtime")): ("staging", "runtime"),
    }
    parts = known_steps.get(name)
    if parts is None:
        return None
    module_name = ".".join(("scripts", "ci", "step_" + "_".join(parts)))
    return getattr(import_module(module_name), "run")


def handler_for_step(name: str) -> StepHandler:
    if name in _REGISTRY:
        return _REGISTRY[name]
    lazy = _lazy_handler(name)
    if lazy is not None:
        return lazy
    raise KeyError(f"unknown step: {name}")


__all__ = ["StepHandler", "handler_for_step"]
