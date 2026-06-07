from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.economics.objective import normalize_objective
from core.growth.campaign_builder.service import AutopilotCampaignBuilder

Json = dict[str, Any]


@dataclass(frozen=True)
class BuiltAdsSpec:
    spec: Json
    notes: str = ""


class AdsAutopilotCampaignBuilder:
    """Adapter that turns high-level autopilot inputs into an AdsSpec.

    Delegates to core.growth.campaign_builder.AutopilotCampaignBuilder which is already canonical.
    """

    def __init__(self, builder: AutopilotCampaignBuilder) -> None:
        self._builder = builder

    def build(self, *, objective: str, offer: Json, audience: Json, channels: list[str]) -> BuiltAdsSpec:
        req = {
            "objective": normalize_objective(objective),
            "offer": dict(offer or {}),
            "audience": dict(audience or {}),
            "channels": list(channels or []),
        }
        spec = self._builder.build(req)  # returns JSON ads spec
        if not isinstance(spec, dict):
            spec = {"spec": spec}
        return BuiltAdsSpec(spec=dict(spec), notes="ok")
