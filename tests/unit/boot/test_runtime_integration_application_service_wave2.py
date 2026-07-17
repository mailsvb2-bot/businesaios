from __future__ import annotations

from types import SimpleNamespace

from boot.runtime_integration import RuntimeIntegration


class _DecisionExecutionPort:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, envelope: object) -> dict:
        self.calls.append(envelope)
        return {"status": "executed", "envelope": envelope}


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


def _envelope():
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            action="noop@v1",
        )
    )


def test_runtime_integration_builds_application_service_from_runtime_exports(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "boot.runtime_integration.bootstrap_runtime",
        lambda: _BootstrapResult(),
    )

    built_runtime, application_service = RuntimeIntegration().build()
    envelope = _envelope()
    result = application_service.execute_action(envelope)

    assert built_runtime.exports.decision_execution.calls == [envelope]
    assert result == {"status": "executed", "envelope": envelope}
    assert application_service.startup_audit_events() == (
        "booted",
        "ready",
    )
