from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from observability.export_pipeline.clickhouse_exporter import ClickHouseExporterConfig
from reliability.redis_idempotency_backend import RedisIdempotencyBackend, RedisIdempotencyConfig
from runtime.backends.postgres_backend import ProductionPostgresBackend, ProductionPostgresBackendConfig
from runtime.firewall.import_guard import ALLOW_INTERNAL_IMPORT
from security.secret_contract import SecretRef
from security.secret_vault import SecretVault

CANON_PROVIDER_RUNTIME_ACTIVATION = True


def _load_internal_attr(module_name: str, attr_name: str) -> Any:
    token = ALLOW_INTERNAL_IMPORT.set(True)
    try:
        module = __import__(module_name, fromlist=[attr_name])
        return getattr(module, attr_name)
    finally:
        ALLOW_INTERNAL_IMPORT.reset(token)


def _http_transport_helpers() -> tuple[Any, Any]:
    return (
        _load_internal_attr('runtime._internal.http_transport', 'form_urlencode'),
        _load_internal_attr('runtime._internal.http_transport', 'sync_request'),
    )


@dataclass(frozen=True)
class ProviderRuntimeActivationService:
    secret_vault: SecretVault

    def activate(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, probe_mode: str = 'dry_run') -> dict[str, Any]:
        normalized_mode = str(probe_mode or 'dry_run').strip().lower() or 'dry_run'
        dry_run = normalized_mode != 'live'
        if provider.provider_key == 'postgres_runtime':
            dsn = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.dsn')
            backend = ProductionPostgresBackend(ProductionPostgresBackendConfig(dsn=dsn))
            result = backend.healthcheck(dry_run=dry_run)
            return {'runtime_kind': 'postgres', 'probe_mode': normalized_mode, 'health': result, 'runtime_hooks': ('sql_healthcheck', 'session_factory', 'admin_runtime_binding')}
        if provider.provider_key == 'redis_runtime':
            redis_url = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.redis_url')
            token = self._read_optional_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.redis_token')
            client = self._build_redis_client(redis_url=redis_url, token=token)
            backend = RedisIdempotencyBackend(client=client, config=RedisIdempotencyConfig(redis_url=redis_url, token=token))
            result = backend.healthcheck(dry_run=dry_run)
            return {'runtime_kind': 'redis', 'probe_mode': normalized_mode, 'health': result, 'runtime_hooks': ('idempotency_cas', 'lease_coordination', 'queue_pressure_runtime')}
        if provider.provider_key == 'clickhouse_export':
            endpoint = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.endpoint')
            database = self._read_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.database')
            username = self._read_optional_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.username')
            password = self._read_optional_secret(tenant_id=tenant_id, connector_id=provider.connector_id, business_id=business_id, secret_name=f'{provider.connector_id}.password')
            config = ClickHouseExporterConfig(endpoint=endpoint, database=database, username=username, password=password)
            result = self._clickhouse_healthcheck(config=config, dry_run=dry_run)
            return {'runtime_kind': 'clickhouse', 'probe_mode': normalized_mode, 'health': result, 'runtime_hooks': ('event_export', 'fleet_reporting', 'analytics_rollups')}
        return {'runtime_kind': 'none', 'probe_mode': normalized_mode, 'health': {'status': 'unsupported', 'provider_key': provider.provider_key}, 'runtime_hooks': ()}

    def _read_secret(self, *, tenant_id: str, connector_id: str, business_id: str, secret_name: str) -> str:
        ref = SecretRef(tenant_id=tenant_id, connector_id=connector_id, scope=business_id, secret_name=secret_name)
        value = self.secret_vault.get(ref).decode('utf-8').strip()
        if not value:
            raise ValueError(f'missing secret value: {secret_name}')
        return value

    def _read_optional_secret(self, *, tenant_id: str, connector_id: str, business_id: str, secret_name: str) -> str | None:
        try:
            return self._read_secret(tenant_id=tenant_id, connector_id=connector_id, business_id=business_id, secret_name=secret_name)
        except Exception:
            return None

    @staticmethod
    def _build_redis_client(*, redis_url: str, token: str | None) -> Any:
        import redis
        kwargs: dict[str, Any] = {'decode_responses': True}
        if token:
            kwargs['password'] = token
        return redis.Redis.from_url(redis_url, **kwargs)

    @staticmethod
    def _clickhouse_healthcheck(*, config: ClickHouseExporterConfig, dry_run: bool) -> dict[str, Any]:
        config.validate()
        if dry_run:
            return {'status': 'ready_for_credentials', 'backend': 'clickhouse', 'database': config.database, 'table': config.table}
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        if config.username:
            import base64
            token = base64.b64encode(f"{config.username}:{config.password or ''}".encode('utf-8')).decode('ascii')
            headers['Authorization'] = f'Basic {token}'
        form_urlencode, sync_request = _http_transport_helpers()
        response = sync_request(
            method='POST',
            url=config.endpoint,
            headers=headers,
            body=form_urlencode({'query': 'SELECT 1'}),
            timeout_s=5,
        )
        if response.error_kind:
            return {
                'status': 'degraded',
                'backend': 'clickhouse',
                'database': config.database,
                'table': config.table,
                'error': response.error_message or response.error_kind,
            }
        body = str(response.text or '').strip()
        return {'status': 'ok' if body.startswith('1') else 'degraded', 'backend': 'clickhouse', 'database': config.database, 'table': config.table, 'response': body[:32]}


__all__ = ['CANON_PROVIDER_RUNTIME_ACTIVATION', 'ProviderRuntimeActivationService']
