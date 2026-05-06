from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from runtime.runtime_observability import RuntimeObservability


@dataclass
class StructureWatchService:
    observability: RuntimeObservability

    def inspect(self, values: Mapping[str, float] | None = None) -> dict[str, float]:
        payload = dict(values or {"curvature": 0.22, "boundary_pressure": 0.28, "blast_radius_risk": 0.16})
        for key, value in payload.items():
            self.observability.record_model_snapshot(
                model_name="structure_watch",
                metric_name=str(key),
                metric_value=float(value),
            )
        return payload
