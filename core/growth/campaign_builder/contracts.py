from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from core.traffic.contracts import TrafficPlan

Json = dict[str, Any]


@dataclass(frozen=True)
class AutopilotCampaignBuildRequest:
    """Input contract for deterministic campaign planning.

    This is *not* a connector contract. It is a business intent that can be translated
    into ads commands via core.traffic.AdsSpecBuilder + core.ads.AdsService.

    All money values are in minor units.
    """

    tenant_id: str
    platform: str
    account_id: str

    what: str
    offer_title: str
    region: str

    total_budget_minor_7d: int
    budget_currency: str

    target_cac_minor: int = 0
    destination: Mapping[str, Any] | None = None

    seed: str = "v1"


@dataclass(frozen=True)
class AutopilotCampaignBuildResult:
    traffic_plan: TrafficPlan
    ads_spec: Json
    notes: str = ""
