from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from application.business_autonomy.business_connector_framework import ConnectorOnboardingService
from application.business_autonomy.onboarding_contract import BusinessOnboardingRequest
from application.business_autonomy.provider_admin_contract import (
    ProviderActivationStatus,
    ProviderCredentialSubmission,
    ProviderDefinition,
)
from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_messaging_binding import describe_provider_messaging_binding
from application.business_autonomy.provider_messaging_metadata import messaging_binding_to_metadata
from core.tenancy.normalization import require_tenant_id
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.provider_connector_health import ProviderConnectorHealthService
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_incident_registry import FileProviderIncidentRegistry
from runtime.business_autonomy.provider_live_probe_runtime import ProviderLiveProbeRuntime
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_pagination_walkers import ProviderPaginationWalkers
from runtime.business_autonomy.provider_queue_execution import ProviderQueueExecutionRuntime
from runtime.business_autonomy.provider_response_parsers import ProviderResponseParsers
from runtime.business_autonomy.provider_secret_versioning import ProviderSecretVersioningService
from runtime.business_autonomy.provider_sync_runtime import ProviderSyncRuntimePlanner
from runtime.business_autonomy.provider_sync_scheduler import ProviderSyncScheduler
from runtime.business_autonomy.provider_transport_bindings import ProviderTransportBindings
from runtime.business_autonomy.provider_vendor_transports import build_provider_vendor_transports
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from runtime.business_autonomy.provider_webhook_route_registry import ProviderWebhookRouteRegistry
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from security.connector_secret_scope import ConnectorSecretScope, SecretAccessOperation, SecretScopeBinding
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import SecretVault

CANON_PROVIDER_ADMIN_SERVICE = True


class ProviderDefinitionRegistry:
    def __init__(self, providers: Mapping[str, ProviderDefinition] | None = None) -> None:
        self._providers = dict(providers or provider_map())

    def get(self, provider_key: str) -> ProviderDefinition:
        provider = self._providers.get(str(provider_key).strip())
        if provider is None:
            raise KeyError(f"unknown provider: {provider_key}")
        provider.validate()
        return provider

    def list(self) -> tuple[ProviderDefinition, ...]:
        return tuple(sorted(self._providers.values(), key=lambda item: (item.domain, item.title)))


@dataclass(frozen=True)
class ProviderAdminService:
    onboarding_service: ConnectorOnboardingService
    secret_vault: SecretVault
    connector_secret_scope: ConnectorSecretScope
    activation_store: Any
    route_state: Any | None = None
    provider_registry: ProviderDefinitionRegistry = field(default_factory=ProviderDefinitionRegistry)

    def list_provider_definitions(self) -> tuple[ProviderDefinition, ...]:
        return self.provider_registry.list()

    def get_activation_status(self, *, tenant_id: str, business_id: str, provider_key: str) -> ProviderActivationStatus | None:
        return self.activation_store.get(tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip(), provider_key=str(provider_key).strip())

    def list_activation_statuses(self, *, tenant_id: str, business_id: str) -> tuple[ProviderActivationStatus, ...]:
        return self.activation_store.list_for_business(tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip())

    def list_provider_secret_history(self, *, tenant_id: str, business_id: str, provider_key: str) -> tuple[dict[str, Any], ...]:
        provider = self.provider_registry.get(provider_key)
        return ProviderSecretVersioningService(self.secret_vault).list_versions(provider=provider, tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip())

    def rollback_provider_secret_version(self, *, tenant_id: str, business_id: str, provider_key: str, secret_name: str, version: str, requested_by: str = 'admin_console') -> dict[str, Any]:
        provider = self.provider_registry.get(provider_key)
        result = ProviderSecretVersioningService(self.secret_vault).rollback_version(provider=provider, tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip(), secret_name=str(secret_name).strip(), version=str(version).strip(), requested_by=str(requested_by).strip() or 'admin_console')
        status = self.reconnect_provider(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, requested_by=requested_by, probe_mode='dry_run', activate_runtime=(provider.domain == 'platform_infra'))
        return {'rollback': result, 'status': status}

    def mark_provider_secret_compromised(self, *, tenant_id: str, business_id: str, provider_key: str, secret_name: str, requested_by: str = 'admin_console', reason: str = 'suspected_compromise') -> dict[str, Any]:
        provider = self.provider_registry.get(provider_key)
        result = ProviderSecretVersioningService(self.secret_vault).mark_compromised(provider=provider, tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip(), secret_name=str(secret_name).strip(), requested_by=str(requested_by).strip() or 'admin_console', reason=str(reason).strip() or 'suspected_compromise')
        status = self.revoke_provider(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, requested_by=requested_by)
        metadata = dict(status.metadata)
        metadata['secret_compromise'] = {'status': result['status'], 'secret_name': result['secret_name'], 'reason': reason}
        final = ProviderActivationStatus(tenant_id=status.tenant_id, business_id=status.business_id, provider_key=status.provider_key, connected=status.connected, connector_id=status.connector_id, title=status.title, channel_kind=status.channel_kind, secret_fields_bound=status.secret_fields_bound, last_updated_utc=status.last_updated_utc, governance_enabled=status.governance_enabled, persistent_surfaces=status.persistent_surfaces, onboarding_ready=status.onboarding_ready, metadata=metadata)
        self.activation_store.put(final)
        return {'compromise': result, 'status': final}

    def schedule_provider_retry(self, *, tenant_id: str, business_id: str, provider_key: str, operation: str, category: str, retryable: bool = True) -> dict[str, Any]:
        result = ProviderSyncScheduler().schedule_retry(provider_key=provider_key, operation=str(operation).strip(), category=str(category).strip(), retryable=bool(retryable), tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip())
        return {'provider_key': result.provider_key, 'operation': result.operation, 'scheduled': result.scheduled, 'status': result.status, 'metadata': dict(result.metadata)}

    def list_provider_retry_jobs(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 20) -> tuple[dict[str, Any], ...]:
        return ProviderSyncScheduler().list_jobs(tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip(), provider_key=str(provider_key).strip(), limit=limit)

    def list_provider_export_history(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 20) -> tuple[dict[str, Any], ...]:
        return ProviderLiveSyncRuntime(self.secret_vault, transports=build_provider_vendor_transports(self.secret_vault)).export_bridge.list_history(tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip(), provider_key=str(provider_key).strip(), limit=limit)

    def list_provider_sync_history(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 20) -> tuple[dict[str, Any], ...]:
        runtime = ProviderLiveSyncRuntime(self.secret_vault, transports=build_provider_vendor_transports(self.secret_vault))
        return runtime.sync_history.list_for_provider(tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip(), provider_key=str(provider_key).strip(), limit=limit)

    def list_provider_runtime_incidents(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]:
        return FileProviderIncidentRegistry().list_for_provider(tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip(), provider_key=str(provider_key).strip(), limit=limit)

    def describe_provider_response_parser(self, *, provider_key: str) -> dict[str, Any]:
        provider = self.provider_registry.get(provider_key)
        return ProviderResponseParsers().describe(provider=provider)

    def probe_provider_live(self, *, tenant_id: str, business_id: str, provider_key: str, mode: str = 'dry_run') -> dict[str, Any]:
        provider = self.provider_registry.get(provider_key)
        runtime = ProviderLiveProbeRuntime(self.secret_vault)
        result = runtime.run(provider=provider, tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip(), mode=str(mode or 'dry_run').strip() or 'dry_run')
        return {'provider_key': result.provider_key, 'mode': result.mode, 'status': result.status, 'ok': result.ok, 'metadata': dict(result.metadata or {})}

    def paginate_provider_sync(self, *, tenant_id: str, business_id: str, provider_key: str, operation: str, mode: str = 'dry_run', payload: Mapping[str, Any] | None = None, max_pages: int = 3) -> dict[str, Any]:
        provider = self.provider_registry.get(provider_key)
        runtime = ProviderLiveSyncRuntime(self.secret_vault, transports=build_provider_vendor_transports(self.secret_vault))
        walker = ProviderPaginationWalkers(runtime=runtime)
        result = walker.walk(provider=provider, tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip(), operation=str(operation).strip(), mode=str(mode or 'dry_run').strip() or 'dry_run', payload=dict(payload or {}), max_pages=max_pages)
        return {'provider_key': result.provider_key, 'operation': result.operation, 'mode': result.mode, 'status': result.status, 'accepted': result.accepted, 'metadata': dict(result.metadata or {})}

    def describe_provider_runtime_routes(self, *, provider_key: str) -> dict[str, Any]:
        provider = self.provider_registry.get(provider_key)
        route_registry = ProviderWebhookRouteRegistry()
        return {
            'provider_key': provider.provider_key,
            'transport_binding': ProviderTransportBindings().describe(provider),
            'webhook_route': route_registry.describe(provider),
            'route_parser': {'supported': True, 'samples': route_registry.extract(provider, headers={}, body=b'{}')},
            'retry_jobs_endpoint': '/control-plane/provider-runtime/retry-jobs',
            'export_history_endpoint': '/control-plane/provider-runtime/export-history',
            'sync_history_endpoint': '/control-plane/provider-runtime/sync-history',
            'response_parser_endpoint': '/control-plane/provider-runtime/response-parser',
            'live_probe_endpoint': '/control-plane/provider-runtime/live-probe',
            'pagination_endpoint': '/control-plane/provider-runtime/paginate',
            'incidents_endpoint': '/control-plane/provider-runtime/incidents',
            'queue_metrics_endpoint': '/control-plane/provider-runtime/queue-metrics',
        }

    def activate_provider(self, submission: ProviderCredentialSubmission) -> ProviderActivationStatus:
        submission.validate()
        provider = self.provider_registry.get(submission.provider_key)
        normalized_tenant = require_tenant_id(submission.tenant_id)
        normalized_business = str(submission.business_id).strip()
        secret_names: list[str] = []
        versioning = ProviderSecretVersioningService(self.secret_vault)
        transport_binding = ProviderTransportBindings().describe(provider)
        webhook_route = ProviderWebhookRouteRegistry().describe(provider)
        for secret_field in provider.secret_fields:
            raw_value = str(submission.secrets.get(secret_field.field_key) or "").strip()
            if secret_field.required and not raw_value:
                raise ValueError(f"missing required secret field: {secret_field.field_key}")
            if not raw_value:
                continue
            versioning.archive_current_secret(provider=provider, tenant_id=normalized_tenant, business_id=normalized_business, secret_name=secret_field.secret_name, requested_by=submission.requested_by, reason='activate_or_update')
            secret_ref = SecretRef(
                tenant_id=normalized_tenant,
                connector_id=provider.connector_id,
                scope=normalized_business,
                secret_name=f"{provider.connector_id}.{secret_field.secret_name}",
            )
            record = SecretRecord(
                ref=secret_ref,
                ciphertext=b"pending",
                source=SecretSource.CONNECTOR,
                metadata={"provider_key": provider.provider_key, "field_key": secret_field.field_key, "business_id": normalized_business},
            )
            self.secret_vault.put(record, plaintext=raw_value.encode("utf-8"))
            secret_names.append(secret_ref.secret_name)
        binding = SecretScopeBinding(
            tenant_id=normalized_tenant,
            connector_id=provider.connector_id,
            allowed_secret_names=tuple(sorted(secret_names)),
            allowed_secret_kinds=tuple(sorted({secret_field.secret_kind for field in provider.secret_fields})),
            allowed_operations=(SecretAccessOperation.READ, SecretAccessOperation.WRITE, SecretAccessOperation.ROTATE),
            metadata={"provider_key": provider.provider_key, "business_id": normalized_business},
        )
        self.connector_secret_scope.register(binding)
        metadata = {
            **dict(submission.metadata or {}),
            "provider_key": provider.provider_key,
            "connector_id": provider.connector_id,
            "verified_owner": bool(submission.metadata.get("verified_owner", True)),
            "non_ai_mode": str(submission.metadata.get("non_ai_mode") or provider.default_non_ai_mode),
            "autonomy_tier": str(submission.metadata.get("autonomy_tier") or ("supervised" if provider.channel_kind.value == "website" else "bounded_autonomy")),
            "action_type": str(submission.metadata.get("action_type") or provider.default_action_type),
            "supports_business_onboarding": bool(provider.supports_business_onboarding),
        }
        persistent_surfaces: tuple[str, ...] = ()
        onboarding_ready = True
        governance_enabled = False
        runtime_activation: dict[str, Any] | None = None
        health_probe = None
        runtime_plan = None
        webhook_contract = None
        live_sync_runner = None
        webhook_replay_guard = None
        if provider.supports_business_onboarding:
            onboarding = self.onboarding_service.onboard(
                BusinessOnboardingRequest(
                    business_id=normalized_business,
                    tenant_id=normalized_tenant,
                    ownership_key=submission.ownership_key,
                    region=str(submission.region or provider.default_region).strip() or provider.default_region,
                    channel_kind=provider.channel_kind,
                    adapter_key=provider.adapter_key,
                    external_ref=submission.external_ref,
                    requested_by=submission.requested_by,
                    metadata=metadata,
                )
            )
            persistent_surfaces = tuple(onboarding.persistent_surfaces)
            onboarding_ready = bool(onboarding.ready)
            governance_enabled = True
            if self.route_state is not None:
                from runtime.business_autonomy.execution_support import ensure_business_route
                region = str(submission.region or provider.default_region).strip() or provider.default_region
                ensure_business_route(
                    route_state=self.route_state,
                    tenant_id=normalized_tenant,
                    business_id=normalized_business,
                    primary_region=region,
                    failover_region="us-east-1" if region != "us-east-1" else "eu-west-1",
                )
        probe_mode = str(submission.metadata.get('probe_mode') or 'dry_run')
        health_probe = ProviderConnectorHealthService(self.secret_vault).probe(
            provider=provider,
            tenant_id=normalized_tenant,
            business_id=normalized_business,
            probe_mode=probe_mode,
        )
        runtime_plan = ProviderSyncRuntimePlanner().describe(provider)
        webhook_contract = ProviderWebhookRuntime(self.secret_vault).describe(provider)
        live_sync_runner = ProviderLiveSyncRuntime(self.secret_vault, transports=build_provider_vendor_transports(self.secret_vault)).describe_runner(provider)
        messaging_binding = describe_provider_messaging_binding(provider)
        webhook_replay_guard = {
            'enabled': bool(webhook_contract.enabled),
            'namespace': 'provider_webhook',
            'scope': 'tenant+business+provider+event_key+payload_digest',
            'verification_kind': webhook_contract.verification_kind,
        }
        if provider.domain == 'platform_infra' or bool(submission.metadata.get('activate_runtime', False)):
            from runtime.business_autonomy.provider_runtime_activation import ProviderRuntimeActivationService
            runtime_activation = ProviderRuntimeActivationService(self.secret_vault).activate(
                provider=provider,
                tenant_id=normalized_tenant,
                business_id=normalized_business,
                probe_mode=probe_mode,
            )
            persistent_surfaces = tuple(sorted(set((*persistent_surfaces, f"runtime:{provider.provider_key}"))))
        status = ProviderActivationStatus(
            tenant_id=normalized_tenant,
            business_id=normalized_business,
            provider_key=provider.provider_key,
            connected=True,
            connector_id=provider.connector_id,
            title=provider.title,
            channel_kind=provider.channel_kind.value,
            secret_fields_bound=tuple(sorted(secret_names)),
            last_updated_utc=datetime.now(UTC).isoformat(),
            governance_enabled=governance_enabled,
            persistent_surfaces=persistent_surfaces,
            onboarding_ready=onboarding_ready,
            metadata={
                "domain": provider.domain,
                "description": provider.description,
                "external_ref": submission.external_ref,
                "non_ai_mode": metadata["non_ai_mode"],
                "autonomy_tier": metadata["autonomy_tier"],
                "requested_by": submission.requested_by,
                "runtime_activation": dict(runtime_activation or {}),
                "health_probe": {
                    'status': health_probe.status,
                    'probe_mode': health_probe.probe_mode,
                    'reason': health_probe.reason,
                    'metadata': dict(health_probe.metadata or {}),
                } if health_probe is not None else {},
                "runtime_plan": {
                    'operations': list(runtime_plan.operations),
                    'read_operations': list(runtime_plan.read_operations),
                    'write_operations': list(runtime_plan.write_operations),
                    'webhook_enabled': runtime_plan.webhook_enabled,
                    'metadata': dict(runtime_plan.metadata or {}),
                } if runtime_plan is not None else {},
                "webhook_contract": {
                    'verification_kind': webhook_contract.verification_kind,
                    'header_names': list(webhook_contract.header_names),
                    'enabled': webhook_contract.enabled,
                    'metadata': dict(webhook_contract.metadata or {}),
                } if webhook_contract is not None else {},
                "live_sync_runner": dict(live_sync_runner or {}),
                "webhook_replay_guard": dict(webhook_replay_guard or {}),
                "transport_binding": transport_binding,
                "messaging_binding": messaging_binding_to_metadata(messaging_binding),
                "webhook_route": webhook_route,
                "secret_versioning": {'enabled': True, 'list_endpoint': '/control-plane/provider-admin/secret-history', 'rollback_endpoint': '/control-plane/provider-admin/secret-rollback'},
            },
        )
        return self.activation_store.put(status)

    def revoke_provider(self, *, tenant_id: str, business_id: str, provider_key: str, requested_by: str = "admin_console") -> ProviderActivationStatus:
        normalized_tenant = require_tenant_id(tenant_id)
        normalized_business = str(business_id).strip()
        provider = self.provider_registry.get(provider_key)
        current = self.activation_store.get(tenant_id=normalized_tenant, business_id=normalized_business, provider_key=provider.provider_key)
        if current is None:
            raise KeyError(f"provider not activated: {provider.provider_key}")
        for secret_field in provider.secret_fields:
            ref = SecretRef(tenant_id=normalized_tenant, connector_id=provider.connector_id, scope=normalized_business, secret_name=f"{provider.connector_id}.{secret_field.secret_name}")
            try:
                self.secret_vault.deactivate(ref)
            except Exception:
                continue
        metadata = {**dict(current.metadata or {}), 'secret_lifecycle': {'last_action': 'revoked', 'requested_by': str(requested_by).strip() or 'admin_console'}}
        status = ProviderActivationStatus(
            tenant_id=current.tenant_id,
            business_id=current.business_id,
            provider_key=current.provider_key,
            connected=False,
            connector_id=current.connector_id,
            title=current.title,
            channel_kind=current.channel_kind,
            secret_fields_bound=current.secret_fields_bound,
            last_updated_utc=datetime.now(UTC).isoformat(),
            governance_enabled=current.governance_enabled,
            persistent_surfaces=current.persistent_surfaces,
            onboarding_ready=False,
            metadata=metadata,
        )
        return self.activation_store.put(status)

    def reconnect_provider(self, *, tenant_id: str, business_id: str, provider_key: str, requested_by: str = "admin_console", probe_mode: str = 'dry_run', activate_runtime: bool = False) -> ProviderActivationStatus:
        normalized_tenant = require_tenant_id(tenant_id)
        normalized_business = str(business_id).strip()
        current = self.activation_store.get(tenant_id=normalized_tenant, business_id=normalized_business, provider_key=provider_key)
        if current is None:
            raise KeyError(f"provider not activated: {provider_key}")
        provider = self.provider_registry.get(provider_key)
        transport_binding = ProviderTransportBindings().describe(provider)
        webhook_route = ProviderWebhookRouteRegistry().describe(provider)
        health_probe = ProviderConnectorHealthService(self.secret_vault).probe(provider=provider, tenant_id=normalized_tenant, business_id=normalized_business, probe_mode=probe_mode)
        runtime_plan = ProviderSyncRuntimePlanner().describe(provider)
        webhook_contract = ProviderWebhookRuntime(self.secret_vault).describe(provider)
        live_sync_runner = ProviderLiveSyncRuntime(self.secret_vault, transports=build_provider_vendor_transports(self.secret_vault)).describe_runner(provider)
        messaging_binding = describe_provider_messaging_binding(provider)
        runtime_activation = {}
        if provider.domain == 'platform_infra' or activate_runtime:
            from runtime.business_autonomy.provider_runtime_activation import ProviderRuntimeActivationService
            runtime_activation = ProviderRuntimeActivationService(self.secret_vault).activate(provider=provider, tenant_id=normalized_tenant, business_id=normalized_business, probe_mode=probe_mode)
        metadata = {
            **dict(current.metadata or {}),
            'health_probe': {'status': health_probe.status, 'probe_mode': health_probe.probe_mode, 'reason': health_probe.reason, 'metadata': dict(health_probe.metadata or {})},
            'runtime_plan': {'operations': list(runtime_plan.operations), 'read_operations': list(runtime_plan.read_operations), 'write_operations': list(runtime_plan.write_operations), 'webhook_enabled': runtime_plan.webhook_enabled, 'metadata': dict(runtime_plan.metadata or {})},
            'webhook_contract': {'verification_kind': webhook_contract.verification_kind, 'header_names': list(webhook_contract.header_names), 'enabled': webhook_contract.enabled, 'metadata': dict(webhook_contract.metadata or {})},
            'live_sync_runner': dict(live_sync_runner or {}),
            'runtime_activation': dict(runtime_activation or {}),
            'transport_binding': transport_binding,
            'messaging_binding': messaging_binding_to_metadata(messaging_binding),
            'webhook_route': webhook_route,
            'secret_versioning': {'enabled': True, 'list_endpoint': '/control-plane/provider-admin/secret-history', 'rollback_endpoint': '/control-plane/provider-admin/secret-rollback'},
            'live_probe': {'endpoint': '/control-plane/provider-runtime/live-probe', 'supported': True},
            'pagination': {'endpoint': '/control-plane/provider-runtime/paginate', 'supported': True},
            'secret_lifecycle': {'last_action': 'reconnected', 'requested_by': str(requested_by).strip() or 'admin_console'},
        }
        connected = health_probe.status not in {'missing_required_secrets', 'invalid_secret_shape', 'misconfigured'}
        status = ProviderActivationStatus(
            tenant_id=current.tenant_id,
            business_id=current.business_id,
            provider_key=current.provider_key,
            connected=connected,
            connector_id=current.connector_id,
            title=current.title,
            channel_kind=current.channel_kind,
            secret_fields_bound=current.secret_fields_bound,
            last_updated_utc=datetime.now(UTC).isoformat(),
            governance_enabled=current.governance_enabled,
            persistent_surfaces=current.persistent_surfaces,
            onboarding_ready=connected and current.onboarding_ready,
            metadata=metadata,
        )
        return self.activation_store.put(status)

    def rotate_provider_secrets(self, *, tenant_id: str, business_id: str, provider_key: str, secrets: Mapping[str, str], requested_by: str = "admin_console") -> ProviderActivationStatus:
        normalized_tenant = require_tenant_id(tenant_id)
        normalized_business = str(business_id).strip()
        provider = self.provider_registry.get(provider_key)
        current = self.activation_store.get(tenant_id=normalized_tenant, business_id=normalized_business, provider_key=provider.provider_key)
        if current is None:
            raise KeyError(f"provider not activated: {provider.provider_key}")
        normalized_secrets = {str(k): str(v) for k, v in dict(secrets or {}).items() if str(k).strip()}
        if not normalized_secrets:
            raise ValueError('secrets are required for rotation')
        updated_fields = []
        versioning = ProviderSecretVersioningService(self.secret_vault)
        for secret_field in provider.secret_fields:
            raw_value = normalized_secrets.get(secret_field.field_key)
            if raw_value is None:
                raw_value = normalized_secrets.get(secret_field.secret_name)
            if raw_value is None:
                continue
            if secret_field.required and not str(raw_value).strip():
                raise ValueError(f'missing required secret field: {secret_field.field_key}')
            versioning.archive_current_secret(provider=provider, tenant_id=normalized_tenant, business_id=normalized_business, secret_name=secret_field.secret_name, requested_by=requested_by, reason='rotate')
            ref = SecretRef(tenant_id=normalized_tenant, connector_id=provider.connector_id, scope=normalized_business, secret_name=f"{provider.connector_id}.{secret_field.secret_name}")
            record = SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR, metadata={'provider_key': provider.provider_key, 'field_key': secret_field.field_key, 'rotated_by': str(requested_by).strip() or 'admin_console'})
            self.secret_vault.put(record, plaintext=str(raw_value).encode('utf-8'))
            updated_fields.append(secret_field.secret_name)
        if not updated_fields:
            raise ValueError('no matching provider secret fields supplied')
        refreshed = self.reconnect_provider(tenant_id=normalized_tenant, business_id=normalized_business, provider_key=provider.provider_key, requested_by=requested_by, probe_mode='dry_run', activate_runtime=provider.domain == 'platform_infra')
        metadata = {**dict(refreshed.metadata or {}), 'secret_lifecycle': {'last_action': 'rotated', 'requested_by': str(requested_by).strip() or 'admin_console', 'updated_fields': tuple(sorted(updated_fields))}}
        status = ProviderActivationStatus(
            tenant_id=refreshed.tenant_id, business_id=refreshed.business_id, provider_key=refreshed.provider_key, connected=refreshed.connected, connector_id=refreshed.connector_id, title=refreshed.title, channel_kind=refreshed.channel_kind, secret_fields_bound=refreshed.secret_fields_bound, last_updated_utc=refreshed.last_updated_utc, governance_enabled=refreshed.governance_enabled, persistent_surfaces=refreshed.persistent_surfaces, onboarding_ready=refreshed.onboarding_ready, metadata=metadata,
        )
        return self.activation_store.put(status)

    def trigger_provider_sync(self, *, tenant_id: str, business_id: str, provider_key: str, operation: str, mode: str = 'dry_run', payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        provider = self.provider_registry.get(provider_key)
        runtime = ProviderLiveSyncRuntime(self.secret_vault, transports=build_provider_vendor_transports(self.secret_vault))
        result = runtime.run(provider=provider, tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip(), operation=str(operation).strip(), mode=str(mode or 'dry_run').strip() or 'dry_run', payload=dict(payload or {}))
        return {'provider_key': result.provider_key, 'operation': result.operation, 'mode': result.mode, 'status': result.status, 'accepted': result.accepted, 'metadata': dict(result.metadata or {})}

    def ingest_provider_webhook(self, *, tenant_id: str, business_id: str, provider_key: str, headers: Mapping[str, str], body: bytes, event_key: str, topic: str = '', owner_id: str = 'provider_admin') -> dict[str, Any]:
        provider = self.provider_registry.get(provider_key)
        ingress = ProviderInboundWebhookService(webhook_runtime=ProviderWebhookRuntime(self.secret_vault), replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()))
        route_registry = ProviderWebhookRouteRegistry()
        normalized_headers = {str(k): str(v) for k, v in dict(headers or {}).items()}
        extracted = route_registry.extract(provider, normalized_headers, bytes(body))
        result = ingress.ingest(provider=provider, tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip(), headers=normalized_headers, body=bytes(body), event_key=str(event_key).strip() or extracted['event_key'], topic=str(topic).strip() or extracted['topic'], owner_id=str(owner_id).strip() or 'provider_admin')
        return {'provider_key': result.provider_key, 'event_key': result.event_key, 'accepted': result.accepted, 'status': result.status, 'metadata': {**dict(result.metadata or {}), 'route_extract': extracted}}

    def enqueue_provider_sync(self, *, tenant_id: str, business_id: str, provider_key: str, operation: str, mode: str = 'live', payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        provider = self.provider_registry.get(provider_key)
        runtime = ProviderLiveSyncRuntime(self.secret_vault, transports=build_provider_vendor_transports(self.secret_vault))
        queue_runtime = ProviderQueueExecutionRuntime(self.secret_vault, live_runtime=runtime)
        result = queue_runtime.enqueue_sync(provider=provider, tenant_id=require_tenant_id(tenant_id), business_id=str(business_id).strip(), operation=str(operation).strip(), mode=str(mode or 'live').strip() or 'live', payload=dict(payload or {}))
        return {'job_id': result.job_id, 'queued': result.queued, 'status': result.status, 'metadata': dict(result.metadata)}

    def tick_provider_sync_queue(self, *, tenant_id: str) -> dict[str, Any]:
        runtime = ProviderLiveSyncRuntime(self.secret_vault, transports=build_provider_vendor_transports(self.secret_vault))
        queue_runtime = ProviderQueueExecutionRuntime(self.secret_vault, live_runtime=runtime)
        registry = {item.provider_key: item for item in self.provider_registry.list()}
        return queue_runtime.tick(provider_registry=registry, tenant_id=require_tenant_id(tenant_id))

    def list_provider_queue_jobs(self, *, tenant_id: str, business_id: str | None = None, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]:
        runtime = ProviderLiveSyncRuntime(self.secret_vault, transports=build_provider_vendor_transports(self.secret_vault))
        queue_runtime = ProviderQueueExecutionRuntime(self.secret_vault, live_runtime=runtime)
        return queue_runtime.list_jobs(tenant_id=require_tenant_id(tenant_id), business_id=None if business_id in {None, ''} else str(business_id).strip(), provider_key=str(provider_key).strip(), limit=limit)

    def describe_provider_live_client(self, *, provider_key: str) -> dict[str, Any]:
        provider = self.provider_registry.get(provider_key)
        transport = build_provider_vendor_transports(self.secret_vault).get(provider.provider_key)
        return {
            'provider_key': provider.provider_key,
            'network_capable': transport is not None,
            'transport_type': None if transport is None else type(transport).__name__,
            'requires_live_flag': True,
            'queue_dispatch_endpoint': '/control-plane/provider-runtime/queue-dispatch',
            'queue_tick_endpoint': '/control-plane/provider-runtime/queue-tick',
            'queue_jobs_endpoint': '/control-plane/provider-runtime/queue-jobs',
            'sync_history_endpoint': '/control-plane/provider-runtime/sync-history',
            'response_parser_endpoint': '/control-plane/provider-runtime/response-parser',
            'live_probe_endpoint': '/control-plane/provider-runtime/live-probe',
            'pagination_endpoint': '/control-plane/provider-runtime/paginate',
            'incidents_endpoint': '/control-plane/provider-runtime/incidents',
            'queue_metrics_endpoint': '/control-plane/provider-runtime/queue-metrics',
        }


__all__ = ["CANON_PROVIDER_ADMIN_SERVICE", "ProviderAdminService", "ProviderDefinitionRegistry"]
