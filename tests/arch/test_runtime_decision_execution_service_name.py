from __future__ import annotations

from pathlib import Path

from bootstrap.runtime_service_specs import get_runtime_service_spec
from runtime.registry import RuntimeRegistry
from runtime.runtime_policies import RuntimePolicies
from runtime.service_names import RuntimeServiceName, canonical_runtime_service_name
from runtime.service_types import RuntimeServiceType

ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = ROOT / "boot" / "registrations" / "register_decision_core.py"


def test_decision_core_runtime_service_name_is_compat_alias_only() -> None:
    assert RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE == "runtime_decision_execution_service"
    assert canonical_runtime_service_name(RuntimeServiceName.DECISION_CORE) == RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE
    assert canonical_runtime_service_name(RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE) == RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE


def test_registry_preserves_legacy_lookup_without_storing_decision_core_name() -> None:
    service = object()
    registry = RuntimeRegistry()
    registry.begin_registration()

    registry.register(
        name=RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE,
        service=service,
        service_type=RuntimeServiceType.EXECUTOR,
    )

    assert registry.get(RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE) is service
    assert registry.get(RuntimeServiceName.DECISION_CORE) is service
    assert registry.has(RuntimeServiceName.DECISION_CORE) is True
    assert registry.service_type_of(RuntimeServiceName.DECISION_CORE) == RuntimeServiceType.EXECUTOR
    assert RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE in registry.list_service_names()
    assert RuntimeServiceName.DECISION_CORE not in registry.list_service_names()


def test_manifest_uses_execution_service_name_not_decision_core_owner_name() -> None:
    spec = get_runtime_service_spec(RuntimeServiceName.DECISION_CORE)

    assert spec.service_name == RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE
    assert spec.service_type == RuntimeServiceType.EXECUTOR
    assert spec.callable_name == "register_decision_core"


def test_runtime_policy_requires_execution_service_not_decision_core_alias() -> None:
    required = RuntimePolicies().required_services

    assert RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE in required
    assert RuntimeServiceName.DECISION_CORE not in required


def test_registration_does_not_register_governed_execution_under_decision_core_name() -> None:
    text = REGISTRATION.read_text(encoding="utf-8")

    assert "name=RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE" in text
    assert "name=RuntimeServiceName.DECISION_CORE" not in text
    assert "CANON_REGISTER_DECISION_CORE_SERVICE_NAME_COMPAT_ALIAS_ONLY" in text
