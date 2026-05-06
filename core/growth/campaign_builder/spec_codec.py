from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from core.traffic.ads_spec_builder import AdsSpecBuilder
from core.traffic.contracts import TrafficPlan

Json = Dict[str, Any]


@dataclass(frozen=True)
class TrafficToAdsSpec:
    """Pure codec: TrafficPlan -> AdsService spec dict."""

    builder: AdsSpecBuilder

    def encode(self, *, plan: TrafficPlan) -> Json:
        return self.builder.to_spec(plan=plan)
