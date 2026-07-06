from __future__ import annotations

from core.marketing.feature_registry_autopilot import FEATURES as AUTOPILOT_FEATURES
from core.marketing.feature_registry_campaigns import FEATURES as CAMPAIGN_FEATURES
from core.marketing.feature_registry_channels import FEATURES as CHANNEL_FEATURES
from core.marketing.feature_registry_pricing import FEATURES as PRICING_FEATURES
from core.marketing.feature_registry_shared import FeatureSpec

FEATURES_200: list[FeatureSpec] = [
    *CHANNEL_FEATURES,
    *CAMPAIGN_FEATURES,
    *PRICING_FEATURES,
    *AUTOPILOT_FEATURES,
]


def feature_map() -> dict[str, FeatureSpec]:
    return {f.name: f for f in FEATURES_200}
