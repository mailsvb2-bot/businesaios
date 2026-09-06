from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from interfaces.api.fastapi_app_factory import create_fastapi_app
from interfaces.api.fastapi_dependencies import FastAPIDependencyContainer
from interfaces.api.health_handler import HealthHandler
from observability.metrics import InMemoryMetrics
from tests.api._authenticated_command_fixture import build_authenticated_command_binding


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
    container = FastAPIDependencyContainer(
        boot_result=_BootResultStub(decision_application=service),
        authenticated_decision_command_binding=build_authenticated_command_binding(),
    )
    app = create_fastapi_app(application_service=service, dependency_container=container)
    client = TestClient(app)
    assert client.get('/health').status_code == 200
    assert client.get('/readyz').status_code == 200
    schema = client.get('/openapi.json').json()
    assert 'securitySchemes' in schema.get('components', {})


def _build_test_client() -> TestClient:
    service = _AppService()
    container = FastAPIDependencyContainer(
        boot_result=_BootResultStub(decision_application=service),
        authenticated_decision_command_binding=build_authenticated_command_binding(),
    )
    return TestClient(create_fastapi_app(application_service=service, dependency_container=container))


def test_release_manifest_route_serves_exact_valid_manifest(monkeypatch, tmp_path) -> None:
    import json

    import adapters.api.fastapi.public_core_routes as public_core_routes

    manifest = {
        'schema_version': 1,
        'commit_sha': 'a' * 40,
        'files': {
            'index.html': '1' * 64,
            'assets/index.js': '2' * 64,
        },
    }
    path = tmp_path / 'release-manifest.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    monkeypatch.setattr(public_core_routes, '_frontend_release_manifest_path', lambda: path)

    response = _build_test_client().get('/release-manifest.json')
    assert response.status_code == 200
    assert response.json() == manifest


def test_release_manifest_route_fails_closed_when_manifest_is_missing(monkeypatch, tmp_path) -> None:
    import adapters.api.fastapi.public_core_routes as public_core_routes

    monkeypatch.setattr(public_core_routes, '_frontend_release_manifest_path', lambda: tmp_path / 'missing.json')
    response = _build_test_client().get('/release-manifest.json')
    assert response.status_code == 503
    assert response.json() == {'detail': 'release_manifest_unavailable'}
