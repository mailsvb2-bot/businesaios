"""Registry bridge for market-intelligence managed runtime.

This module is lifecycle/attachment only. It must not introduce planning,
provider routing, or any alternate decision path. The runtime registry already
owns service registration; this bridge only binds the managed market-
intelligence runtime to the canonical market-watch service when available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.runtime_observability import RuntimeObservability
from runtime.service_names import RuntimeServiceName

CANON_MARKET_INTELLIGENCE_RUNTIME_REGISTRY_BRIDGE = True
CANON_MARKET_INTELLIGENCE_RUNTIME_REGISTRY_BRIDGE_NO_DECISION_LOGIC = True

@dataclass(frozen=True)
class MarketIntelligenceRuntimeAttachmentReport:
    attached: bool
    registry_service_name: str
    attached_runtime_type: str | None
    market_watch_type: str | None


def attach_market_intelligence_runtime_to_registry(
    *,
    registry: Any,
    runtime: Any,
    observability: RuntimeObservability | None = None,
    service_name: str = RuntimeServiceName.MARKET_WATCH,
) -> MarketIntelligenceRuntimeAttachmentReport:
    if registry is None:
        raise ValueError('registry is required')
    if runtime is None:
        raise ValueError('runtime is required')
    resolved_service_name = str(service_name).strip() or RuntimeServiceName.MARKET_WATCH
    if not hasattr(registry, 'has') or not hasattr(registry, 'get'):
        raise TypeError('registry must expose has() and get()')
    if not registry.has(resolved_service_name):
        return MarketIntelligenceRuntimeAttachmentReport(
            attached=False,
            registry_service_name=resolved_service_name,
            attached_runtime_type=type(runtime).__name__,
            market_watch_type=None,
        )
    market_watch = registry.get(resolved_service_name)
    if not hasattr(market_watch, 'attach_market_intelligence_runtime'):
        raise TypeError('registered market-watch service cannot attach managed runtime')
    market_watch.attach_market_intelligence_runtime(runtime)
    if observability is not None:
        observability.record_audit_event(
            'market_intelligence_runtime_attached_to_registry',
            registry_service_name=resolved_service_name,
            market_watch_type=type(market_watch).__name__,
            runtime_type=type(runtime).__name__,
        )
    return MarketIntelligenceRuntimeAttachmentReport(
        attached=True,
        registry_service_name=resolved_service_name,
        attached_runtime_type=type(runtime).__name__,
        market_watch_type=type(market_watch).__name__,
    )


__all__ = [
    'CANON_MARKET_INTELLIGENCE_RUNTIME_REGISTRY_BRIDGE',
    'CANON_MARKET_INTELLIGENCE_RUNTIME_REGISTRY_BRIDGE_NO_DECISION_LOGIC',
    'MarketIntelligenceRuntimeAttachmentReport',
    'attach_market_intelligence_runtime_to_registry',
]
