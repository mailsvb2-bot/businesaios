from __future__ import annotations

from typing import Any, Protocol


GROWTH_RECOMMENDATION_CONTRACT_VERSION = "GR-CONTRACT-V1"


class GrowthRecommendationPort(Protocol):
    def build_recommendations(
        self,
        tenant_id: str,
        correlation_id: str,
        payload: dict[str, object] | None = None,
    ) -> Any: ...
