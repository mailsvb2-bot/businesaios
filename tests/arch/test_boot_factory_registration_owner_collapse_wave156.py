from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def test_boot_package_roots_export_catalog_runtime_metadata() -> None:
    factories = _read("boot/factories/__init__.py")
    registrations = _read("boot/registrations/__init__.py")
    for needle in [
        "FACTORY_FUNCTIONS",
        "FACTORY_SERVICE_NAMES",
        "LOCAL_FACTORY_FUNCTION_NAMES",
        "get_factory_for_service",
        "build_runtime_decision_execution_service",
    ]:
        assert needle in factories
    for needle in [
        "CATALOG_REGISTRATION_FUNCTION_NAMES",
        "CATALOG_REGISTRATION_FUNCTIONS",
        "register_runtime_decision_execution_service",
    ]:
        assert needle in registrations


def test_tests_prefer_boot_package_roots_and_runtime_application_root() -> None:
    relpaths = [
        "tests/boot/test_runtime_service_specs_alignment.py",
        "tests/boot/test_factory_catalog_service_lookup.py",
        "tests/unit/runtime/test_runtime_application_contracts_single_path_wave3.py",
        "tests/unit/runtime/test_runtime_application_contracts_raw_builder_wave3.py",
        "tests/unit/runtime/test_runtime_application_ports_builders_wave3.py",
        "tests/unit/test_core_runtime_action_result_presenter_wave104.py",
        "tests/unit/test_core_runtime_action_result_errors_wave102.py",
        "tests/test_ai_ceo_plan_contract.py",
        "tests/test_runtime_action_enforcement.py",
    ]
    for relpath in relpaths:
        text = _read(relpath)
        assert "from boot.factories._catalog_owner import " not in text
        assert "from boot.registrations._catalog_owner import " not in text
        assert "from runtime.application import " in text or "from boot.factories import " in text or "from boot.registrations import " in text or "from core.actions import " in text
        assert "from runtime.application.contracts import " not in text


def test_runtime_decision_registration_uses_canonical_factory_name() -> None:
    text = _read("boot/registrations/register_decision_core.py")
    assert "build_runtime_decision_execution_service" in text
    assert "from boot.factories import build_decision_core" not in text


def test_factory_and_registration_roots_export_runtime_decision_execution_surfaces() -> None:
    import importlib

    factory_root = importlib.import_module("boot.factories")
    factory_submodule = importlib.import_module("boot.factories.decision_core_factory")
    assert factory_root.build_runtime_decision_execution_service is factory_submodule.build_runtime_decision_execution_service

    registration_root = importlib.import_module("boot.registrations")
    registration_submodule = importlib.import_module("boot.registrations.register_decision_core")
    assert registration_root.register_runtime_decision_execution_service is registration_submodule.register_runtime_decision_execution_service
