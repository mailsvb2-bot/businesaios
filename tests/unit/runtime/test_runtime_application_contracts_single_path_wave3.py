from __future__ import annotations

from types import SimpleNamespace

from runtime.application import (
    ReadOnlyRuntimeRegistry,
    build_runtime_application_service,
)
from runtime.service_names import RuntimeServiceName


class _DecisionExecutionOwner:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, envelope: object) -> dict:
        self.calls.append(envelope)
        return {"status": "executed", "envelope": envelope}


class _AuditLog:
    def event_names(self):
        return ("booted", "ready")


class _Observability:
    def __init__(self) -> None:
        self.audit_log = _AuditLog()


class _Registry:
    def __init__(self) -> None:
        self.execution_owner = _DecisionExecutionOwner()
        self._services = {
            RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE: (
                self.execution_owner
            ),
            RuntimeServiceName.OBSERVABILITY: _Observability(),
        }

    def get(self, name: str):
        return self._services[name]

    def has(self, name: str) -> bool:
        return name in self._services

    def service_type_of(self, name: str) -> str:
        return name

    def dependencies_of(self, name: str):
        del name
        return ()

    def list_service_names(self):
        return tuple(self._services)

    def snapshot(self):
        return dict(self._services)


def _envelope():
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            action="ping@v1",
        )
    )


def test_build_runtime_application_service_routes_envelope_through_runtime_ports() -> None:
    registry = _Registry()
    service = build_runtime_application_service(
        ReadOnlyRuntimeRegistry(registry)
    )
    envelope = _envelope()

    result = service.execute_action(envelope)

    assert result["status"] == "executed"
    assert registry.execution_owner.calls == [envelope]
    assert service.startup_audit_events() == ("booted", "ready")
