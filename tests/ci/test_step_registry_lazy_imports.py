from __future__ import annotations

from scripts.ci import step_ids
from scripts.ci import step_doctor
from scripts.ci import step_registry


def test_step_registry_exposes_all_canonical_step_ids() -> None:
    assert set(step_ids.all_step_names()) == set(step_registry.all_step_names())


def test_step_registry_handlers_are_lazy_wrappers() -> None:
    handler = step_registry.handler_for_step("boot-smoke")
    assert handler.__name__.startswith("lazy_step_boot_smoke")

def test_doctor_legacy_wrapper_keeps_lazy_registry_export() -> None:
    assert step_doctor.run is step_registry.run_doctor
    assert step_registry.run_doctor.__name__.startswith("lazy_doctor_run_doctor")

