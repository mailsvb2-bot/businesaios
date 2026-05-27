from __future__ import annotations

import importlib

from application.decision.action_dispatcher import ActionDispatcher as CanonicalActionDispatcher
from application.decision.action_dispatcher import ActionDispatcher as CoreActionDispatcher
from application.decision.action_validator import ActionValidator as CanonicalActionValidator
from application.decision.action_validator import ActionValidator as CoreActionValidator
from application.decision.decision_service import DecisionApplicationService as CanonicalDecisionApplicationService
from application.decision.ports import (
    DecisionExecutionPortProtocol as CanonicalDecisionExecutionPortProtocol,
)
from application.decision.ports import (
    DecisionExecutionPortProtocol as CoreDecisionExecutionPortProtocol,
)
from application.decision.ports import (
    ObservabilityPortProtocol as CanonicalObservabilityPortProtocol,
)
from application.decision.ports import (
    ObservabilityPortProtocol as CoreObservabilityPortProtocol,
)
from core.application.decision_service import DecisionApplicationService as CoreDecisionApplicationService
from runtime.application.action_dispatcher import ActionDispatcher as RuntimeActionDispatcher
from runtime.application.application_ports import (
    DecisionExecutionPortProtocol as RuntimeDecisionExecutionPortProtocol,
)
from runtime.application.application_ports import (
    ObservabilityPortProtocol as RuntimeObservabilityPortProtocol,
)
from runtime.application.application_service import DecisionApplicationService as RuntimeDecisionApplicationService
from runtime.platform.support.serving.runtime.action_validator import ActionValidator as RuntimeActionValidator


class _DecisionExecutionPort:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def decide_and_execute(self, action: object) -> dict:
        self.calls.append(action)
        return {"status": "executed", "action": action}


class _ObservabilityPort:
    def audit_events(self) -> tuple[str, ...]:
        return ("booted", "ready")


class _Action:
    pass


def test_runtime_application_surface_reexports_core_owned_types() -> None:
    assert RuntimeActionDispatcher is CanonicalActionDispatcher
    assert RuntimeDecisionApplicationService is CanonicalDecisionApplicationService
    assert RuntimeDecisionExecutionPortProtocol is CanonicalDecisionExecutionPortProtocol
    assert RuntimeObservabilityPortProtocol is CanonicalObservabilityPortProtocol
    assert RuntimeActionValidator is CanonicalActionValidator


def test_core_application_service_preserves_runtime_contract() -> None:
    execution_port = _DecisionExecutionPort()
    observability_port = _ObservabilityPort()
    action = _Action()

    service = CoreDecisionApplicationService(
        decision_execution_port=execution_port,
        observability_port=observability_port,
    )

    result = service.execute_action(action)

    assert result == {"status": "executed", "action": action}
    assert execution_port.calls == [action]
    assert service.startup_audit_events() == ("booted", "ready")


def test_core_action_validator_preserves_non_none_semantics() -> None:
    validator = CoreActionValidator()

    assert validator.valid(object()) is True
    assert validator.valid(None) is False


def test_runtime_application_legacy_submodule_imports_resolve_via_package_aliases() -> None:
    assert importlib.import_module("runtime.application.action_dispatcher") is importlib.import_module(
        "application.decision.action_dispatcher"
    )
    assert importlib.import_module("runtime.application.application_ports") is importlib.import_module(
        "application.decision.ports"
    )
    assert importlib.import_module("runtime.application.application_service") is importlib.import_module(
        "application.decision.decision_service"
    )
