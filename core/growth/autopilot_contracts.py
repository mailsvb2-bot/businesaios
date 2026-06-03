from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from collections.abc import Mapping

from kernel.decisioning.decision_types import RecommendationSet


@dataclass(frozen=True)
class GrowthAutopilotContext:
    tenant_id: str
    correlation_id: str
    payload: Mapping[str, Any]


class GrowthRecommendationBuilderPort(Protocol):
    def build(self, context: GrowthAutopilotContext) -> RecommendationSet:
        ...
