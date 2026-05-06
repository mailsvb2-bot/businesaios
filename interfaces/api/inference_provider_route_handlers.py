from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.inference.providers.provider_health_monitor import InferenceProviderHealthMonitor


CANON_API_INFERENCE_PROVIDER_ROUTE_HANDLERS = True


@dataclass(frozen=True)
class InferenceProviderRouteHandlers:
    provider_health_monitor: InferenceProviderHealthMonitor

    def list_provider_health(self) -> dict[str, Any]:
        snapshots = self.provider_health_monitor.snapshots()
        return {
            'providers': tuple(
                {
                    'provider_name': item.provider_name,
                    'healthy': bool(item.healthy),
                    'availability_score': float(item.availability_score),
                    'latency_score': float(item.latency_score),
                    'error_rate': float(item.error_rate),
                    'saturation_score': float(item.saturation_score),
                }
                for item in snapshots
            ),
            'read_only': True,
        }
