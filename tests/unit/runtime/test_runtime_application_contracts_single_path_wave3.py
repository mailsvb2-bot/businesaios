from __future__ import annotations

from runtime.application import ReadOnlyRuntimeRegistry, build_runtime_application_service


class _DecisionCore:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def decide_and_execute(self, action: object) -> dict:
        self.calls.append(action)
        return {"status": "executed", "action": action}


class _AuditLog:
    def event_names(self):
        return ("booted", "ready")


class _Observability:
    def __init__(self) -> None:
        self.audit_log = _AuditLog()


class _Registry:
    def __init__(self) -> None:
        self._services = {
            "decision_core": _DecisionCore(),
            "observability": _Observability(),
        }

    def get(self, name: str):
        return self._services[name]

    def has(self, name: str) -> bool:
        return name in self._services

    def service_type_of(self, name: str) -> str:
        return name

    def dependencies_of(self, name: str):
        return ()

    def list_service_names(self):
        return tuple(self._services)

    def snapshot(self):
        return dict(self._services)


def test_build_runtime_application_service_routes_through_runtime_ports() -> None:
    registry = ReadOnlyRuntimeRegistry(_Registry())
    service = build_runtime_application_service(registry)
    result = service.execute_action({"kind": "ping"})
    assert result["status"] == "executed"
    assert service.startup_audit_events() == ("booted", "ready")
