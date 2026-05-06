from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.base import ConnectorEffectorBase
from interfaces.ads.google_ads_connector import GoogleAdsConnector


@dataclass
class UpdateBudgetEffector(ConnectorEffectorBase):
    action_type: str = "update_budget"
    external_system: str = "google_ads"
    connector: GoogleAdsConnector = field(default_factory=GoogleAdsConnector)
    operation: str = "update_budget"
