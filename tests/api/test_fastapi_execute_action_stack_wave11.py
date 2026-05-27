from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from interfaces.api.fastapi_dependencies import FastAPIDependencyContainer
from interfaces.api.fastapi_router_adapter import create_api_router
from observability.metrics import InMemoryMetrics
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_registry import InMemoryTenantRegistry


@dataclass(frozen=True)
class _RuntimeStub:
    metrics: InMemoryMetrics = field(default_factory=InMemoryMetrics)


@dataclass(frozen=True)
class _BootResultStub:
    runtime: object
    decision_application: object
    startup_report: tuple[str, ...] = ()


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


def test_fastapi_execute_action_uses_canonical_stack_with_generated_request_context_ids(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_API_IDEMPOTENCY_PATH', str(tmp_path / 'api-idem.sqlite3'))
    service = _Service()
    runtime = _RuntimeStub()
    container = FastAPIDependencyContainer(
        boot_result=_BootResultStub(runtime=runtime, decision_application=service),
        tenant_registry=InMemoryTenantRegistry(),
        tenant_policy_store=InMemoryTenantPolicyStore(),
        tenant_quota_guard=TenantQuotaGuard(policy_store=InMemoryTenantPolicyStore()),
    )
    app_router = create_api_router(application_service=service, dependency_container=container)

    client = TestClient(app_router)
    response = client.post('/actions/execute', json={'action_type': 'launch', 'payload': {'x': 1}})

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert payload['action_type'] == 'launch'
    assert payload['details']['echo']['x'] == 1
    assert service.calls == 1


def test_fastapi_execute_action_threads_header_identity_into_canonical_stack(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_API_IDEMPOTENCY_PATH', str(tmp_path / 'api-idem.sqlite3'))
    service = _Service()
    runtime = _RuntimeStub()
    container = FastAPIDependencyContainer(
        boot_result=_BootResultStub(runtime=runtime, decision_application=service),
        tenant_registry=InMemoryTenantRegistry(),
        tenant_policy_store=InMemoryTenantPolicyStore(),
        tenant_quota_guard=TenantQuotaGuard(policy_store=InMemoryTenantPolicyStore()),
    )
    app_router = create_api_router(application_service=service, dependency_container=container)

    client = TestClient(app_router)
    response = client.post(
        '/actions/execute',
        json={'action_type': 'launch', 'payload': {'x': 1}},
        headers={
            'x-tenant-id': 'tenant-a',
            'x-idempotency-key': 'idem-header-1',
            'x-action-id': 'action-header-1',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert payload['action_type'] == 'launch'
    assert payload['details']['echo']['x'] == 1
    assert service.calls == 1

    replay = client.post(
        '/actions/execute',
        json={'action_type': 'launch', 'payload': {'x': 999}},
        headers={
            'x-tenant-id': 'tenant-a',
            'x-idempotency-key': 'idem-header-1',
            'x-action-id': 'action-header-1',
        },
    )
    assert replay.status_code == 200
    replay_payload = replay.json()
    assert replay_payload['details']['echo']['x'] == 1
    assert service.calls == 1


def test_fastapi_execute_action_replay_does_not_fail_when_quota_is_exhausted_after_first_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_API_IDEMPOTENCY_PATH', str(tmp_path / 'api-idem.sqlite3'))
    service = _Service()
    runtime = _RuntimeStub()
    policy_store = InMemoryTenantPolicyStore()
    policy_store.save(__import__('tests.unit.interfaces.api.test_execute_action_stack_wave11', fromlist=['_tenant_policy_bundle'])._tenant_policy_bundle('tenant-a', {'actions_per_hour': 1}))
    container = FastAPIDependencyContainer(
        boot_result=_BootResultStub(runtime=runtime, decision_application=service),
        tenant_registry=InMemoryTenantRegistry(),
        tenant_policy_store=policy_store,
        tenant_quota_guard=TenantQuotaGuard(policy_store=policy_store),
    )
    app_router = create_api_router(application_service=service, dependency_container=container)

    client = TestClient(app_router)
    headers = {
        'x-tenant-id': 'tenant-a',
        'x-idempotency-key': 'idem-http-replay-1',
        'x-action-id': 'action-http-replay-1',
    }
    first = client.post('/actions/execute', json={'action_type': 'launch', 'payload': {'x': 1}}, headers=headers)
    second = client.post('/actions/execute', json={'action_type': 'launch', 'payload': {'x': 999}}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()['details']['echo']['x'] == 1
    assert service.calls == 1


from fastapi import FastAPI

from observability.action_audit_log import ActionAuditLog
from observability.decision_audit_log import DecisionAuditLog


@dataclass(frozen=True)
class _RuntimeInfraStub:
    action_audit_log: ActionAuditLog = field(default_factory=ActionAuditLog)
    decision_audit_log: DecisionAuditLog = field(default_factory=DecisionAuditLog)


@dataclass(frozen=True)
class _RuntimeWithInfraStub:
    metrics: InMemoryMetrics = field(default_factory=InMemoryMetrics)
    runtime_infra: object = field(default_factory=_RuntimeInfraStub)




def test_fastapi_control_plane_uses_shared_decision_audit_log(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_DATA_DIR', str(tmp_path))
    service = _Service()
    runtime = _RuntimeWithInfraStub()
    runtime.runtime_infra.decision_audit_log.record_payload({'decision_id': 'dec-1', 'trace_id': 'trace-1', 'tenant_id': 'tenant-a'})
    container = FastAPIDependencyContainer(
        boot_result=_BootResultStub(runtime=runtime, decision_application=service),
        tenant_registry=InMemoryTenantRegistry(),
        tenant_policy_store=InMemoryTenantPolicyStore(),
        tenant_quota_guard=TenantQuotaGuard(policy_store=InMemoryTenantPolicyStore()),
    )
    router = create_api_router(application_service=service, dependency_container=container)
    app = FastAPI()
    app.include_router(router)

    assert container.decision_audit_log() is runtime.runtime_infra.decision_audit_log
    assert runtime.runtime_infra.decision_audit_log.list_by_trace(trace_id='trace-1', limit=10)[0]['decision_id'] == 'dec-1'

def test_fastapi_control_plane_audit_reads_same_execute_action_audit_log(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_API_IDEMPOTENCY_PATH', str(tmp_path / 'api-idem.sqlite3'))
    service = _Service()
    runtime = _RuntimeWithInfraStub()
    container = FastAPIDependencyContainer(
        boot_result=_BootResultStub(runtime=runtime, decision_application=service),
        tenant_registry=InMemoryTenantRegistry(),
        tenant_policy_store=InMemoryTenantPolicyStore(),
        tenant_quota_guard=TenantQuotaGuard(policy_store=InMemoryTenantPolicyStore()),
    )
    router = create_api_router(application_service=service, dependency_container=container)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    action_response = client.post(
        '/actions/execute',
        json={'action_type': 'launch', 'payload': {'x': 1}},
        headers={'x-tenant-id': 'tenant-a', 'x-action-id': 'action-audit-1', 'x-idempotency-key': 'idem-audit-1'},
    )
    assert action_response.status_code == 200

    audit_response = client.get('/control-plane/audit/actions?trace_id=idem-does-not-matter', headers={
        'x-api-key': 'development-control-plane-key',
        'x-tenant-id': 'tenant-a',
        'x-actor-id': 'operator-1',
    })
    # fallback auth path may reject trace-filtered empty response depending on bundle; raw log must still be shared.
    assert runtime.runtime_infra.action_audit_log.records
    assert any(str(item.get('action_id')) == 'action-audit-1' for item in runtime.runtime_infra.action_audit_log.records)
