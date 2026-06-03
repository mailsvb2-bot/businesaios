from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from runtime.runtime_observability import RuntimeObservability


@dataclass
class FlowWatchService:
    observability: RuntimeObservability

    def inspect(self, values: Mapping[str, float] | None = None) -> dict[str, float]:
        payload = dict(values or {"velocity": 0.57, "pressure": 0.34, "turbulence": 0.14})
        for key, value in payload.items():
            self.observability.record_model_snapshot(
                model_name="flow_watch",
                metric_name=str(key),
                metric_value=float(value),
            )
        return payload
