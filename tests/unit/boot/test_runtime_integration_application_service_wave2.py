from __future__ import annotations

from boot.runtime_integration import RuntimeIntegration


class _DecisionExecutionPort:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def decide_and_execute(self, action: object) -> dict:
        self.calls.append(action)
        return {"status": "executed", "action": action}


class _ObservabilityPort:
    def audit_events(self) -> tuple[str, ...]:
        return ("booted", "ready")


class _Exports:
    def __init__(self) -> None:
        self.decision_execution = _DecisionExecutionPort()
        self.observability = _ObservabilityPort()


class _BuiltRuntime:
    def __init__(self) -> None:
        self.exports = _Exports()


class _Artifacts:
    def __init__(self) -> None:
        self.built_runtime = _BuiltRuntime()


class _BootstrapResult:
    def __init__(self) -> None:
        self.artifacts = _Artifacts()


def test_runtime_integration_builds_application_service_from_runtime_exports(monkeypatch) -> None:
    monkeypatch.setattr("boot.runtime_integration.bootstrap_runtime", lambda: _BootstrapResult())

    built_runtime, application_service = RuntimeIntegration().build()

    action = object()
    result = application_service.execute_action(action)

    assert built_runtime.exports.decision_execution.calls == [action]
    assert result == {"status": "executed", "action": action}
    assert application_service.startup_audit_events() == ("booted", "ready")
