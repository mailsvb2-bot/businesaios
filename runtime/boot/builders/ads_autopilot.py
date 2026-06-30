from __future__ import annotations

from runtime.ads import AdsAutopilotCampaignBuilder, AdsAutopilotEngine, AdsService, AutopilotCampaignBuilder

CANON_BOOT_WIRING_ONLY = True

def build_ads_autopilot_engine(*, ads: AdsService, campaign_builder: AutopilotCampaignBuilder) -> AdsAutopilotEngine:
    return AdsAutopilotEngine(ads=ads, builder=AdsAutopilotCampaignBuilder(campaign_builder))
