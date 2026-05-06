from __future__ import annotations

from dataclasses import dataclass, field

from interfaces.api.runtime_api_bundle import build_runtime_api_bundle
from observability.action_audit_log import ActionAuditLog
from observability.decision_audit_log import DecisionAuditLog
from observability.metrics import InMemoryMetrics


class _Service:
    def __init__(self) -> None:
        self.calls = 0

    def execute_action(self, action):
        self.calls += 1
        return {
            'status': 'ok',
            'action_type': action.action_type,
            'reason': 'executed',
            'details': {'echo': dict(action.payload)},
        }

    def startup_audit_events(self):
        return ()


@dataclass(frozen=True)
class _RuntimeInfraStub:
    action_audit_log: ActionAuditLog = field(default_factory=ActionAuditLog)
    decision_audit_log: DecisionAuditLog = field(default_factory=DecisionAuditLog)


@dataclass(frozen=True)
class _RuntimeStub:
    metrics: InMemoryMetrics = field(default_factory=InMemoryMetrics)
    runtime_infra: object = field(default_factory=_RuntimeInfraStub)


@dataclass(frozen=True)
class _BootResultStub:
    runtime: object
    decision_application: object
    startup_report: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ContainerStub:
    boot_result: object
    tenant_quota_guard: object | None = None
    api_idempotency_store: object | None = None


def test_runtime_api_bundle_builds_shared_runtime_adapter_and_handlers() -> None:
    service = _Service()
    container = _ContainerStub(boot_result=_BootResultStub(runtime=_RuntimeStub(), decision_application=service))
    bundle = build_runtime_api_bundle(application_service=service, dependency_container=container)

    assert bundle.runtime_adapter.application_service is service
    assert bundle.handler_bundle.route_handlers.application_service is service
    assert bundle.handler_bundle.execute_action_port_provider is not None
    assert bundle.execution_path_lock is not None


def test_runtime_api_bundle_runtime_adapter_health_uses_same_service() -> None:
    service = _Service()
    bundle = build_runtime_api_bundle(application_service=service, dependency_container=None)
    payload = bundle.runtime_adapter.health()
    assert payload['startup_audit_events'] == []
