from __future__ import annotations

from typing import Callable

from scripts.ci import step_ids as _step_ids
from scripts.ci.doctor import run_doctor
from scripts.ci.step_build_artifact import run as run_build_artifact
from scripts.ci.step_canon_audit import run as run_canon_audit
from scripts.ci.step_demo_e2e_smoke import run as run_demo_e2e_smoke
from scripts.ci.step_dependency_lock import run as run_dependency_lock
from scripts.ci.step_import_smoke import run as run_import_smoke
from scripts.ci.step_integration_tests import run as run_integration_tests
from scripts.ci.step_lock_tests import run as run_lock_tests
from scripts.ci.step_project_shape import run as run_project_shape
from scripts.ci.step_quality import run as run_quality
from scripts.ci.step_unit_tests import run as run_unit_tests
from scripts.ci.step_verify_release import run as run_verify_release

StepHandler = Callable[[], tuple[bool, str]]


_REGISTRY: dict[str, StepHandler] = {
    _step_ids.project_shape(): run_project_shape,
    _step_ids.dependency_lock(): run_dependency_lock,
    _step_ids.doctor(): run_doctor,
    _step_ids.import_smoke(): run_import_smoke,
    _step_ids.demo_e2e_smoke(): run_demo_e2e_smoke,
    _step_ids.quality(): run_quality,
    _step_ids.canon_audit(): run_canon_audit,
    _step_ids.lock_tests(): run_lock_tests,
    _step_ids.unit_tests(): run_unit_tests,
    _step_ids.integration_tests(): run_integration_tests,
    _step_ids.verify_release(): run_verify_release,
    _step_ids.build_artifact(): run_build_artifact,
}


def handler_for_step(name: str) -> StepHandler:
    if name not in _REGISTRY:
        raise KeyError(f"unknown step: {name}")
    return _REGISTRY[name]


__all__ = ["StepHandler", "handler_for_step"]
