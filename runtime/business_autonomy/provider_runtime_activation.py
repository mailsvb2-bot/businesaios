from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from observability.export_pipeline.clickhouse_exporter import ClickHouseExporterConfig
from reliability.redis_idempotency_backend import RedisIdempotencyBackend, RedisIdempotencyConfig
from runtime.backends.postgres_backend import ProductionPostgresBackend, ProductionPostgresBackendConfig
from runtime.effects import encode_form_body
from runtime.handler_loader import import_internal_attr
from security.secret_contract import SecretRef
from security.secret_vault import SecretVault

CANON_PROVIDER_RUNTIME_ACTIVATION = True


def _load_internal_attr(module_name: str, attr_name: str) -> Any:
    return import_internal_attr(module_name, attr_name)


def _http_transport_helpers() -> Any:
    return _load_internal_attr('runtime._internal.http_transport', 'sync_request')


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
        if dry_run:
            return {'status': 'dry_run', 'endpoint': config.endpoint, 'database': config.database}
        sync_request = _http_transport_helpers()
        body = encode_form_body({'query': 'SELECT 1'})
        response = sync_request(
            url=str(config.endpoint),
            method='POST',
            body=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout_s=10.0,
        )
        return {'status': 'ok' if int(response.get('status_code', 0)) < 400 else 'error', 'status_code': response.get('status_code')}


__all__ = ['CANON_PROVIDER_RUNTIME_ACTIVATION', 'ProviderRuntimeActivationService']
