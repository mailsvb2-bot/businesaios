from __future__ import annotations

from typing import Protocol

from runtime.decisioning import RecommendationSet


class AdsAutopilotProposalPort(Protocol):
    def build(
        self,
        tenant_id: str,
        correlation_id: str,
        payload: dict[str, object] | None = None,
    ) -> RecommendationSet:
        ...
