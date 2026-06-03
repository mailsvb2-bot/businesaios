from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from runtime.runtime_observability import RuntimeObservability


@dataclass
class ArchitectureWatchService:
    observability: RuntimeObservability

    def inspect(self, values: Mapping[str, float] | None = None) -> dict[str, float]:
        payload = dict(values or {"global_stability": 0.82, "change_pressure": 0.18})
        for key, value in payload.items():
            self.observability.record_model_snapshot(
                model_name="architecture_watch",
                metric_name=str(key),
                metric_value=float(value),
            )
        return payload
