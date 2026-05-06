from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from bootstrap.system_boot_surface import build_system_boot_surface
from entrypoints.api.api_key_policy import PersistentApiKeyStore
from governance.rbac_contract import RoleId
from tenancy.tenant_contract import TenantPlan, TenantRecord, TenantStatus
from tenancy.tenant_registry import PersistentTenantRegistry

ROOT = Path(__file__).resolve().parents[2]


def test_systemd_units_define_server_contract() -> None:
    expected = {
        'deploy/systemd/businesaios-api.service',
        'deploy/systemd/businesaios-telegram.service',
        'deploy/systemd/businesaios-evolution.service',
    }
    for rel in expected:
        text = (ROOT / rel).read_text(encoding='utf-8')
        assert 'ExecStartPre=/opt/businesaios/.venv/bin/python -m scripts.server.migrate_before_start' in text
        assert 'ExecStart=/opt/businesaios/.venv/bin/python -m scripts.server.run_profile' in text
        assert 'Restart=on-failure' in text
        assert 'StandardOutput=journal' in text
        assert 'WorkingDirectory=/opt/businesaios' in text


def test_env_example_covers_server_and_secret_contract() -> None:
    text = (ROOT / '.env.example').read_text(encoding='utf-8')
    for key in (
        'APP_ENV=prod',
        'METRO_DB_ENGINE=postgres',
        'DATABASE_URL=',
        'POSTGRES_DSN=',
        'TELEGRAM_BOT_TOKEN=',
        'CONTROL_PLANE_API_KEY=',
        'BUSINESAIOS_DATA_DIR=',
    ):
        assert key in text


def test_server_boot_surface_supports_health_readiness_and_execute_flow(monkeypatch, tmp_path) -> None:
    tenant_path = tmp_path / 'tenant_registry.json'
    api_key_path = tmp_path / 'api_keys.json'
    monkeypatch.setenv('BUSINESAIOS_TENANT_REGISTRY_PATH', str(tenant_path))
    monkeypatch.setenv('BUSINESAIOS_API_KEY_STORE_PATH', str(api_key_path))
    tenant_registry = PersistentTenantRegistry(path=tenant_path)
    tenant_registry.register(TenantRecord(tenant_id='tenant-a', display_name='Tenant A', plan=TenantPlan.ENTERPRISE, status=TenantStatus.ACTIVE))
    api_key_store = PersistentApiKeyStore(path=api_key_path)
    _, control_plane_api_key = api_key_store.issue(
        tenant_id='tenant-a',
        subject='deployment-contract-control-plane',
        actor_id='deployment-contract-control-plane',
        roles=(RoleId.OWNER,),
        scopes=('control_plane:read', 'control_plane:admin'),
        display_name='Deployment contract control-plane principal',
        metadata={'test': 'server_deployment_contract'},
    )
    auth_headers = {
        'X-API-Key': control_plane_api_key,
        'X-Tenant-ID': 'tenant-a',
        'X-Forwarded-Proto': 'https',
    }
    surface = build_system_boot_surface()
    with TestClient(surface.http_app) as client:
        assert client.get('/health').status_code == 200
        ready = client.get('/readyz')
        assert ready.status_code == 200
        assert ready.json()['status'] == 'ready'
        result = client.post(
            '/actions/execute',
            json={'action_type': 'pricing.publish_offer', 'payload': {'offer_id': 'srv-1', 'amount': 199}},
            headers={'x-tenant-id': 'tenant-a', 'x-idempotency-key': 'srv-test-1', 'x-action-id': 'srv-test-action-1'},
        )
        assert result.status_code == 200
        payload = result.json()
        assert str(payload.get('status') or '').lower() not in {'error', 'failed'}
        audit = client.get('/control-plane/audit/actions', headers=auth_headers)
        assert audit.status_code == 200
        assert 'records' in audit.json()
