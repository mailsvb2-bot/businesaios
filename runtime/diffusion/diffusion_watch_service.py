from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from runtime.runtime_observability import RuntimeObservability


@dataclass
class DiffusionWatchService:
    observability: RuntimeObservability

    def inspect(self, values: Mapping[str, float] | None = None) -> dict[str, float]:
        payload = dict(values or {"spread_index": 0.44, "saturation_risk": 0.19, "viral_potential": 0.37})
        for key, value in payload.items():
            self.observability.record_model_snapshot(
                model_name="diffusion_watch",
                metric_name=str(key),
                metric_value=float(value),
            )
        return payload
