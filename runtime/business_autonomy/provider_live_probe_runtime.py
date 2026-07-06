from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_runtime_contract import ProviderLiveProbeResult
from runtime.business_autonomy.provider_connector_health import ProviderConnectorHealthService
from runtime.business_autonomy.provider_http_live_clients import VendorHttpLiveTransport, build_live_http_transports
from runtime.business_autonomy.provider_incident_registry import FileProviderIncidentRegistry
from runtime.business_autonomy.provider_probe_result_enricher import (
    enrich_probe_result_with_messaging_health,
    finalize_probe_result,
)
from runtime.business_autonomy.provider_runtime_observability import ProviderRuntimeObservability
from runtime.business_autonomy.provider_transport_bindings import ProviderTransportBindings
from security.secret_vault import SecretVault

CANON_PROVIDER_LIVE_PROBE_RUNTIME = True


@dataclass(frozen=True)
class ProviderLiveProbeRuntime:
    secret_vault: SecretVault
    transports: Mapping[str, VendorHttpLiveTransport] = field(default_factory=dict)
    incident_registry: FileProviderIncidentRegistry = field(default_factory=FileProviderIncidentRegistry)
    observability: ProviderRuntimeObservability = field(default_factory=ProviderRuntimeObservability)
    channel_health_registry: Any | None = None

    def __post_init__(self) -> None:
        if not self.transports:
            object.__setattr__(self, 'transports', build_live_http_transports(self.secret_vault, bind_live_network=False))

    def describe(self, *, provider: ProviderDefinition) -> dict[str, Any]:
        binding = ProviderTransportBindings().describe(provider)
        return {
            'provider_key': provider.provider_key,
            'probe_supported': provider.provider_key in self.transports,
            'probe_path': binding.get('probe_path'),
            'base_url': binding.get('base_url'),
            'live_network_default': False,
            'modes': ('dry_run', 'live'),
        }

    def run(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, mode: str = 'dry_run') -> ProviderLiveProbeResult:
        normalized_mode = str(mode or 'dry_run').strip().lower() or 'dry_run'
        health = ProviderConnectorHealthService(self.secret_vault).probe(provider=provider, tenant_id=tenant_id, business_id=business_id, probe_mode=normalized_mode)
        binding = ProviderTransportBindings().describe(provider)
        transport = self.transports.get(provider.provider_key)
        if transport is None:
            incident = self.incident_registry.append({'tenant_id': str(tenant_id), 'business_id': str(business_id), 'provider_key': provider.provider_key, 'kind': 'probe', 'status': 'probe_unsupported', 'severity': 'major', 'category': 'probe', 'message': 'probe transport unsupported', 'metadata': {'binding': binding}})
            result = ProviderLiveProbeResult(provider_key=provider.provider_key, mode=normalized_mode, status='probe_unsupported', ok=False, metadata={'binding': binding, 'health_probe': {'status': health.status, 'reason': health.reason}, 'incident': incident})
            return finalize_probe_result(observability=self.observability, tenant_id=str(tenant_id), provider_key=provider.provider_key, mode=normalized_mode, result=result)
        if health.status in {'missing_required_secrets', 'invalid_secret_shape', 'misconfigured'}:
            incident = self.incident_registry.append({'tenant_id': str(tenant_id), 'business_id': str(business_id), 'provider_key': provider.provider_key, 'kind': 'probe', 'status': 'probe_rejected_misconfigured', 'severity': 'major', 'category': 'probe', 'message': health.reason, 'metadata': {'binding': binding, 'health_status': health.status}})
            result = ProviderLiveProbeResult(provider_key=provider.provider_key, mode=normalized_mode, status='probe_rejected_misconfigured', ok=False, metadata={'binding': binding, 'health_probe': {'status': health.status, 'reason': health.reason}, 'incident': incident})
            result = enrich_probe_result_with_messaging_health(registry=self.channel_health_registry, provider=provider, probe_result=result)
            return finalize_probe_result(observability=self.observability, tenant_id=str(tenant_id), provider_key=provider.provider_key, mode=normalized_mode, result=result)
        payload = {'_allow_network': normalized_mode == 'live', '_probe': True}
        response = dict(transport.execute(provider=provider, tenant_id=str(tenant_id), business_id=str(business_id), operation='health_probe', payload=payload) or {})
        if response.get('_prepared_only'):
            result = ProviderLiveProbeResult(provider_key=provider.provider_key, mode=normalized_mode, status='probe_prepared_only', ok=(normalized_mode != 'live'), metadata={'binding': binding, 'response': response, 'health_probe': {'status': health.status, 'reason': health.reason}})
            result = enrich_probe_result_with_messaging_health(registry=self.channel_health_registry, provider=provider, probe_result=result)
            return finalize_probe_result(observability=self.observability, tenant_id=str(tenant_id), provider_key=provider.provider_key, mode=normalized_mode, result=result)
        http_status = response.get('http_status')
        ok = http_status is None or 200 <= int(http_status) < 300
        incident = None
        if not ok:
            incident = self.incident_registry.append({'tenant_id': str(tenant_id), 'business_id': str(business_id), 'provider_key': provider.provider_key, 'kind': 'probe', 'status': 'probe_live_failed', 'severity': 'major', 'category': 'probe', 'message': str(response.get('error_message') or 'probe failed'), 'metadata': {'binding': binding, 'response': response}})
        result = ProviderLiveProbeResult(provider_key=provider.provider_key, mode=normalized_mode, status='probe_live_ok' if ok else 'probe_live_failed', ok=ok, metadata={'binding': binding, 'response': response, 'health_probe': {'status': health.status, 'reason': health.reason}, 'incident': incident})
        result = enrich_probe_result_with_messaging_health(registry=self.channel_health_registry, provider=provider, probe_result=result)
        return finalize_probe_result(observability=self.observability, tenant_id=str(tenant_id), provider_key=provider.provider_key, mode=normalized_mode, result=result)


__all__ = ['CANON_PROVIDER_LIVE_PROBE_RUNTIME', 'ProviderLiveProbeRuntime']
