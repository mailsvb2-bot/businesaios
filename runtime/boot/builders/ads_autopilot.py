from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


from runtime.ads import AdsAutopilotCampaignBuilder, AdsAutopilotEngine, AdsService, AutopilotCampaignBuilder


def build_ads_autopilot_engine(*, ads: AdsService, campaign_builder: AutopilotCampaignBuilder) -> AdsAutopilotEngine:
    return AdsAutopilotEngine(ads=ads, builder=AdsAutopilotCampaignBuilder(campaign_builder))
