from __future__ import annotations

from typing import Any, Protocol

ADS_RECOMMENDATION_CONTRACT_VERSION = "AR-CONTRACT-V1"

class AdsRecommendationPort(Protocol):
    def next_actions(self, ctx: Any) -> dict[str, Any]: ...
