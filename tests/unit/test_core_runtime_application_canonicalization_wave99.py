from __future__ import annotations

import importlib
from types import SimpleNamespace

from application.decision.action_dispatcher import (
    ActionDispatcher as CanonicalActionDispatcher,
)
from application.decision.action_validator import (
    ActionValidator as CanonicalActionValidator,
)
from application.decision.action_validator import (
    ActionValidator as CoreActionValidator,
)
from application.decision.decision_service import (
    DecisionApplicationService as CanonicalDecisionApplicationService,
)
from application.decision.ports import (
    DecisionExecutionPortProtocol as CanonicalDecisionExecutionPortProtocol,
)
from application.decision.ports import (
    ObservabilityPortProtocol as CanonicalObservabilityPortProtocol,
)
from core.application.decision_service import (
    DecisionApplicationService as CoreDecisionApplicationService,
)
from runtime.application.action_dispatcher import (
    ActionDispatcher as RuntimeActionDispatcher,
)
from runtime.application.application_ports import (
    DecisionExecutionPortProtocol as RuntimeDecisionExecutionPortProtocol,
)
from runtime.application.application_ports import (
    ObservabilityPortProtocol as RuntimeObservabilityPortProtocol,
)
from runtime.application.application_service import (
    DecisionApplicationService as RuntimeDecisionApplicationService,
)
from runtime.platform.support.serving.runtime.action_validator import (
    ActionValidator as RuntimeActionValidator,
)


class _DecisionExecutionPort:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, envelope: object) -> dict:
        self.calls.append(envelope)
        return {"status": "executed", "envelope": envelope}


class _ObservabilityPort:
    def audit_events(self) -> tuple[str, ...]:
        return ("booted", "ready")


def _envelope():
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            action="noop@v1",
        )
    )


def test_runtime_application_surface_reexports_core_owned_types() -> None:
    assert RuntimeActionDispatcher is CanonicalActionDispatcher
    assert (
        RuntimeDecisionApplicationService
        is CanonicalDecisionApplicationService
    )
    assert (
        RuntimeDecisionExecutionPortProtocol
        is CanonicalDecisionExecutionPortProtocol
    )
    assert (
        RuntimeObservabilityPortProtocol
        is CanonicalObservabilityPortProtocol
    )
    assert RuntimeActionValidator is CanonicalActionValidator


def test_core_application_service_preserves_envelope_runtime_contract() -> None:
    execution_port = _DecisionExecutionPort()
    observability_port = _ObservabilityPort()
    envelope = _envelope()
    service = CoreDecisionApplicationService(
        decision_execution_port=execution_port,
        observability_port=observability_port,
    )

    result = service.execute_action(envelope)

    assert result == {"status": "executed", "envelope": envelope}
    assert execution_port.calls == [envelope]
    assert service.startup_audit_events() == ("booted", "ready")


def test_core_action_validator_requires_canonical_envelope_semantics() -> None:
    validator = CoreActionValidator()

    assert validator.valid(_envelope()) is True
    assert validator.valid(object()) is False
    assert validator.valid(None) is False


def test_runtime_application_legacy_submodule_imports_resolve_via_package_aliases() -> None:
    assert importlib.import_module(
        "runtime.application.action_dispatcher"
    ) is importlib.import_module(
        "application.decision.action_dispatcher"
    )
    assert importlib.import_module(
        "runtime.application.application_ports"
    ) is importlib.import_module("application.decision.ports")
    assert importlib.import_module(
        "runtime.application.application_service"
    ) is importlib.import_module(
        "application.decision.decision_service"
    )
