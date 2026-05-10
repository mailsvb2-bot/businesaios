from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_runtime_contract import ProviderSyncRunResult
from runtime.business_autonomy.provider_error_taxonomy import ProviderErrorTaxonomy
from runtime.business_autonomy.provider_runtime_audit import ProviderRuntimeAuditRecorder
from runtime.business_autonomy.provider_retry_policy import ProviderRetryPolicy
from runtime.business_autonomy.provider_runtime_observability import ProviderRuntimeObservability
from runtime.business_autonomy.provider_connector_health import ProviderConnectorHealthService
from runtime.business_autonomy.provider_transport_bindings import ProviderTransportBindings
from runtime.business_autonomy.provider_runtime_export_bridge import ProviderRuntimeExportBridge
from runtime.business_autonomy.provider_sync_runtime import ProviderSyncRuntimePlanner
from runtime.business_autonomy.provider_sync_scheduler import ProviderSyncScheduler
from runtime.business_autonomy.provider_response_parsers import ProviderResponseParsers
from runtime.business_autonomy.provider_sync_history import ProviderSyncHistory
from runtime.business_autonomy.provider_incident_registry import FileProviderIncidentRegistry
from runtime.business_autonomy.provider_runtime_write_guard import ProviderRuntimeWriteGuard
from security.secret_vault import SecretVault

CANON_PROVIDER_LIVE_SYNC_RUNTIME = True


class ProviderTransportPort(Protocol):
    def execute(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ProviderLiveSyncRuntime:
    secret_vault: SecretVault
    transports: Mapping[str, ProviderTransportPort] = field(default_factory=dict)
    error_taxonomy: ProviderErrorTaxonomy = field(default_factory=ProviderErrorTaxonomy)
    audit_recorder: ProviderRuntimeAuditRecorder = field(default_factory=ProviderRuntimeAuditRecorder.in_memory)
    retry_policy: ProviderRetryPolicy = field(default_factory=ProviderRetryPolicy)
    observability: ProviderRuntimeObservability = field(default_factory=ProviderRuntimeObservability)
    export_bridge: ProviderRuntimeExportBridge = field(default_factory=ProviderRuntimeExportBridge)
    scheduler: ProviderSyncScheduler = field(default_factory=ProviderSyncScheduler)
    response_parsers: ProviderResponseParsers = field(default_factory=ProviderResponseParsers)
    sync_history: ProviderSyncHistory = field(default_factory=ProviderSyncHistory)
    incident_registry: FileProviderIncidentRegistry = field(default_factory=FileProviderIncidentRegistry)
    write_guard: ProviderRuntimeWriteGuard = field(default_factory=ProviderRuntimeWriteGuard)

    def describe_runner(self, provider: ProviderDefinition) -> dict[str, Any]:
        planner = ProviderSyncRuntimePlanner().describe(provider)
        binding = ProviderTransportBindings().describe(provider)
        return {
            'provider_key': provider.provider_key,
            'transport_bound': provider.provider_key in self.transports,
            'dry_run_supported': True,
            'live_run_supported': provider.provider_key in self.transports,
            'operations': list(planner.operations),
            'read_operations': list(planner.read_operations),
            'write_operations': list(planner.write_operations),
            'write_guard': {'enabled': True, 'source': 'runtime.business_autonomy.provider_runtime_write_guard', 'truth_source': 'application.business_autonomy.provider_truth_matrix', 'fail_closed': True},
            'transport_binding': binding,
            'response_parser': self.response_parsers.describe(provider=provider),
        }

    def _finalize_result(self, *, tenant_id: str, business_id: str, provider: ProviderDefinition, operation: str, mode: str, result: ProviderSyncRunResult, payload: Mapping[str, Any]) -> ProviderSyncRunResult:
        refs = self.audit_recorder.record_sync_run(tenant_id=tenant_id, business_id=business_id, provider_key=provider.provider_key, operation=operation, mode=mode, status=result.status, accepted=result.accepted, payload=dict(payload or {}), metadata=dict(result.metadata))
        export_refs = self.export_bridge.export_runtime_event(tenant_id=str(tenant_id), business_id=str(business_id), provider_key=provider.provider_key, event_kind='sync', payload={'operation': operation, 'mode': mode, 'status': result.status, 'accepted': result.accepted})
        history_row = self.sync_history.append({'tenant_id': str(tenant_id), 'business_id': str(business_id), 'provider_key': provider.provider_key, 'operation': operation, 'mode': mode, 'status': result.status, 'accepted': result.accepted, 'recorded_at_utc': refs.get('recorded_at_utc') if isinstance(refs, dict) else None, 'parsed_response': dict(result.metadata.get('parsed_response') or {}), 'transport_response': dict(result.metadata.get('transport_response') or {}), 'error': dict(result.metadata.get('error') or {}), 'retry_policy': dict(result.metadata.get('retry_policy') or {})})
        self.observability.record_sync(tenant_id=str(tenant_id), provider_key=provider.provider_key, operation=operation, status=result.status, accepted=result.accepted, mode=mode)
        if not result.accepted or str(result.status).startswith('live_execution_failed'):
            error_view = dict(result.metadata.get('error') or {})
            retry_view = dict(result.metadata.get('retry_policy') or {})
            incident = self.incident_registry.append({'tenant_id': str(tenant_id), 'business_id': str(business_id), 'provider_key': provider.provider_key, 'kind': 'sync', 'status': result.status, 'severity': 'critical' if str(result.status) == 'live_execution_failed' else 'major', 'category': str(error_view.get('category') or 'sync_runtime'), 'message': str(error_view.get('message') or result.status), 'retryable': bool(retry_view.get('retryable', False)), 'metadata': {'operation': operation, 'mode': mode, 'error': error_view, 'retry_policy': retry_view}})
        else:
            incident = None
        return ProviderSyncRunResult(**{**result.__dict__, 'metadata': {**dict(result.metadata), 'audit_refs': refs, 'export_refs': export_refs, 'history_row': history_row, 'incident': incident}})

    def run(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, operation: str, mode: str = 'dry_run', payload: Mapping[str, Any] | None = None) -> ProviderSyncRunResult:
        planner = ProviderSyncRuntimePlanner().describe(provider)
        normalized_mode = str(mode or 'dry_run').strip().lower() or 'dry_run'
        normalized_operation = str(operation or '').strip()
        if normalized_operation not in planner.operations:
            result = ProviderSyncRunResult(provider_key=provider.provider_key, operation=normalized_operation, mode=normalized_mode, status='unsupported_operation', accepted=False, metadata={'available_operations': list(planner.operations)})
            return self._finalize_result(tenant_id=tenant_id, business_id=business_id, provider=provider, operation=normalized_operation, mode=normalized_mode, result=result, payload=dict(payload or {}))
        binding = ProviderTransportBindings().describe(provider)
        request_base = {'provider_key': provider.provider_key, 'operation': normalized_operation, 'tenant_id': str(tenant_id), 'business_id': str(business_id), 'payload': dict(payload or {}), 'domain': provider.domain, 'adapter_key': provider.adapter_key, 'transport_binding': binding, 'response_parser': self.response_parsers.describe(provider=provider)}
        if normalized_mode == 'live' and provider.provider_key not in self.transports:
            result = ProviderSyncRunResult(provider_key=provider.provider_key, operation=normalized_operation, mode=normalized_mode, status='live_transport_unbound', accepted=False, metadata={'request_envelope': request_base, 'transport_binding': binding})
            return self._finalize_result(tenant_id=tenant_id, business_id=business_id, provider=provider, operation=normalized_operation, mode=normalized_mode, result=result, payload=dict(payload or {}))
        write_guard_decision = self.write_guard.evaluate(provider=provider, operation=normalized_operation, mode=normalized_mode)
        if not write_guard_decision.allowed:
            result = ProviderSyncRunResult(provider_key=provider.provider_key, operation=normalized_operation, mode=normalized_mode, status=write_guard_decision.status, accepted=False, metadata={'provider_write_guard': write_guard_decision.to_metadata(), 'request_envelope': request_base})
            return self._finalize_result(tenant_id=tenant_id, business_id=business_id, provider=provider, operation=normalized_operation, mode=normalized_mode, result=result, payload=dict(payload or {}))
        health = ProviderConnectorHealthService(self.secret_vault).probe(provider=provider, tenant_id=tenant_id, business_id=business_id, probe_mode=normalized_mode)
        if health.status in {'misconfigured', 'invalid_secret_shape'}:
            result = ProviderSyncRunResult(provider_key=provider.provider_key, operation=normalized_operation, mode=normalized_mode, status='rejected_misconfigured', accepted=False, metadata={'health_probe': {'status': health.status, 'reason': health.reason, 'metadata': dict(health.metadata or {})}, 'provider_write_guard': write_guard_decision.to_metadata()})
            return self._finalize_result(tenant_id=tenant_id, business_id=business_id, provider=provider, operation=normalized_operation, mode=normalized_mode, result=result, payload=dict(payload or {}))
        envelope = {**request_base, 'provider_write_guard': write_guard_decision.to_metadata()}
        if normalized_mode != 'live':
            result = ProviderSyncRunResult(provider_key=provider.provider_key, operation=normalized_operation, mode=normalized_mode, status='dry_run_ready', accepted=True, metadata={'request_envelope': envelope, 'health_probe': {'status': health.status, 'reason': health.reason}, 'provider_write_guard': write_guard_decision.to_metadata()})
            return self._finalize_result(tenant_id=tenant_id, business_id=business_id, provider=provider, operation=normalized_operation, mode=normalized_mode, result=result, payload=dict(payload or {}))
        transport = self.transports.get(provider.provider_key)
        if transport is None:
            result = ProviderSyncRunResult(provider_key=provider.provider_key, operation=normalized_operation, mode=normalized_mode, status='live_transport_unbound', accepted=False, metadata={'request_envelope': envelope, 'health_probe': {'status': health.status, 'reason': health.reason}, 'provider_write_guard': write_guard_decision.to_metadata()})
            return self._finalize_result(tenant_id=tenant_id, business_id=business_id, provider=provider, operation=normalized_operation, mode=normalized_mode, result=result, payload=dict(payload or {}))
        try:
            response = dict(transport.execute(provider=provider, tenant_id=str(tenant_id), business_id=str(business_id), operation=normalized_operation, payload=dict(payload or {})) or {})
            parsed_response = dict(response.get('parsed_response') or {})
            if not parsed_response and not response.get('_prepared_only'):
                parsed_response = self.response_parsers.parse(provider=provider, operation=normalized_operation, response=response)
            response['parsed_response'] = parsed_response
            if response.pop('_prepared_only', False):
                result = ProviderSyncRunResult(provider_key=provider.provider_key, operation=normalized_operation, mode=normalized_mode, status='live_prepared_only', accepted=False, metadata={'request_envelope': envelope, 'transport_response': response, 'health_probe': {'status': health.status, 'reason': health.reason}, 'response_parser': self.response_parsers.describe(provider=provider), 'provider_write_guard': write_guard_decision.to_metadata()})
            else:
                result = ProviderSyncRunResult(provider_key=provider.provider_key, operation=normalized_operation, mode=normalized_mode, status='live_executed', accepted=True, metadata={'request_envelope': envelope, 'transport_response': response, 'parsed_response': parsed_response, 'health_probe': {'status': health.status, 'reason': health.reason}, 'response_parser': self.response_parsers.describe(provider=provider), 'provider_write_guard': write_guard_decision.to_metadata()})
        except Exception as exc:
            error_view = self.error_taxonomy.classify(provider_key=provider.provider_key, error=exc)
            retry_decision = self.retry_policy.evaluate(provider_key=provider.provider_key, category=error_view.category, retryable=error_view.retryable)
            scheduled_retry = self.scheduler.schedule_retry(provider_key=provider.provider_key, operation=normalized_operation, category=error_view.category, retryable=error_view.retryable, tenant_id=str(tenant_id), business_id=str(business_id))
            result = ProviderSyncRunResult(provider_key=provider.provider_key, operation=normalized_operation, mode=normalized_mode, status='live_execution_failed', accepted=False, metadata={'request_envelope': envelope, 'health_probe': {'status': health.status, 'reason': health.reason}, 'provider_write_guard': write_guard_decision.to_metadata(), 'error': {'category': error_view.category, 'code': error_view.code, 'retryable': error_view.retryable, 'message': error_view.message, 'metadata': dict(error_view.metadata)}, 'retry_policy': {'category': retry_decision.category, 'retryable': retry_decision.retryable, 'next_delay_seconds': retry_decision.next_delay_seconds, 'max_attempts': retry_decision.max_attempts, 'metadata': dict(retry_decision.metadata)}, 'scheduled_retry': {'scheduled': scheduled_retry.scheduled, 'status': scheduled_retry.status, 'metadata': dict(scheduled_retry.metadata)}})
        return self._finalize_result(tenant_id=tenant_id, business_id=business_id, provider=provider, operation=normalized_operation, mode=normalized_mode, result=result, payload=dict(payload or {}))


__all__ = ['CANON_PROVIDER_LIVE_SYNC_RUNTIME', 'ProviderLiveSyncRuntime', 'ProviderTransportPort']
