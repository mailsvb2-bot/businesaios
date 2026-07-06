from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from interfaces.api.fastapi_app_factory import create_fastapi_app
from interfaces.api.fastapi_dependencies import FastAPIDependencyContainer
from interfaces.api.health_handler import HealthHandler
from observability.metrics import InMemoryMetrics


@dataclass(frozen=True)
class _RuntimeStub:
    metrics: InMemoryMetrics = field(default_factory=InMemoryMetrics)


@dataclass(frozen=True)
class _BootResultStub:
    runtime: object = field(default_factory=_RuntimeStub)
    decision_application: object = None
    startup_report: tuple[str, ...] = ('boot:ok',)


class _AppService:
    def startup_audit_events(self):
        return ('boot:ok',)


def test_health_handler_readiness_uses_startup_events() -> None:
    handler = HealthHandler(application_service=_AppService())
    assert handler.health().status == 'ok'
    assert handler.readiness().status == 'ready'


def test_fastapi_app_factory_registers_security_and_health_routes() -> None:
    service = _AppService()
    container = FastAPIDependencyContainer(boot_result=_BootResultStub(decision_application=service))
    app = create_fastapi_app(application_service=service, dependency_container=container)
    client = TestClient(app)
    assert client.get('/health').status_code == 200
    assert client.get('/readyz').status_code == 200
    schema = client.get('/openapi.json').json()
    assert 'securitySchemes' in schema.get('components', {})
