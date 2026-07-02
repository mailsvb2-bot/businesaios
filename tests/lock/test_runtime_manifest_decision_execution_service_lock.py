from __future__ import annotations

from canon.anti_second_brain_runtime_rules import FORBIDDEN_DIRECT_DECISION_DEPENDENCIES
from canon.runtime_allowed_registrations import ALLOWED_RUNTIME_REGISTRATIONS
from runtime.service_names import RuntimeServiceName
from runtime.service_types import RuntimeServiceType


def test_runtime_decision_execution_service_is_allowed_manifest_owner() -> None:
    assert (
        ALLOWED_RUNTIME_REGISTRATIONS[RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE]
        == RuntimeServiceType.EXECUTOR
    )


def test_decision_core_is_not_allowed_as_boot_manifest_service() -> None:
    assert RuntimeServiceName.DECISION_CORE not in ALLOWED_RUNTIME_REGISTRATIONS


def test_anti_second_brain_rules_bind_to_execution_service_not_decision_core() -> None:
    assert RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE in FORBIDDEN_DIRECT_DECISION_DEPENDENCIES
    assert RuntimeServiceName.DECISION_CORE not in FORBIDDEN_DIRECT_DECISION_DEPENDENCIES
    assert RuntimeServiceName.ACTION_BUDGET in FORBIDDEN_DIRECT_DECISION_DEPENDENCIES[
        RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE
    ]
