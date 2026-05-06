from __future__ import annotations

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import ChannelCapabilityDescriptor, ChannelKind


class CampaignAdsChannelAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.CAMPAIGN_ADS
    adapter_key = "campaign_ads.default"
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor("campaign.launch", ('campaign_launch',), write_enabled=True, human_verification_required=True),
            ChannelCapabilityDescriptor("campaign.metrics", ('campaign_metrics_pull',), write_enabled=False, human_verification_required=False),
        ),
    )
