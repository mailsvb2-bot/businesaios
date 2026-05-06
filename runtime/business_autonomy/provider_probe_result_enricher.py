from __future__ import annotations

from application.business_autonomy.provider_runtime_contract import ProviderLiveProbeResult
from runtime.business_autonomy.provider_messaging_health_bridge import (
    apply_provider_probe_result_to_registry,
    signal_to_metadata,
)


def enrich_probe_result_with_messaging_health(*, registry, provider, probe_result: ProviderLiveProbeResult) -> ProviderLiveProbeResult:
    signal = apply_provider_probe_result_to_registry(
        registry=registry,
        provider=provider,
        probe_result=probe_result,
    ) if registry is not None else None
    return ProviderLiveProbeResult(
        provider_key=probe_result.provider_key,
        mode=probe_result.mode,
        status=probe_result.status,
        ok=probe_result.ok,
        metadata={**dict(probe_result.metadata or {}), 'messaging_health_signal': signal_to_metadata(signal)},
    )


def finalize_probe_result(*, observability, tenant_id: str, provider_key: str, mode: str, result: ProviderLiveProbeResult) -> ProviderLiveProbeResult:
    observability.record_live_probe(
        tenant_id=str(tenant_id),
        provider_key=str(provider_key),
        status=result.status,
        ok=result.ok,
        mode=str(mode),
        metadata=dict(result.metadata or {}),
    )
    return result


__all__ = [
    'enrich_probe_result_with_messaging_health',
    'finalize_probe_result',
]
