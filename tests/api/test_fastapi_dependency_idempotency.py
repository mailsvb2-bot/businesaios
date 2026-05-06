from __future__ import annotations

from dataclasses import dataclass

from interfaces.api.fastapi_dependencies import FastAPIDependencyContainer


@dataclass(frozen=True)
class _Boot:
    decision_application: object


def test_fastapi_dependency_container_exposes_durable_api_idempotency_store(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_API_IDEMPOTENCY_PATH', str(tmp_path / 'api-idem.sqlite3'))
    container = FastAPIDependencyContainer(boot_result=_Boot(decision_application=object()))
    key = container.build_api_idempotency_key(tenant_id='tenant-1', request_id='req-1', payload={'action': 'launch'})
    decision = container.api_idempotency_store.reserve(key=key, owner_id='api-test')
    assert decision.resolution.value == 'accepted'
