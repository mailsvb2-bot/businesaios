from __future__ import annotations

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import ChannelCapabilityDescriptor, ChannelKind

CANON_ADS_PRODUCTION_ADAPTERS = True


class MetaAdsProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.CAMPAIGN_ADS
    adapter_key = 'campaign_ads.meta'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('meta_ads.campaigns', ('campaign_launch', 'campaign_pause', 'campaign_budget_update'), write_enabled=True, human_verification_required=True),
            ChannelCapabilityDescriptor('meta_ads.reporting', ('campaign_report_read',), write_enabled=False, human_verification_required=False),
        ),
    )


class GoogleAdsProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.CAMPAIGN_ADS
    adapter_key = 'campaign_ads.google'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('google_ads.campaigns', ('campaign_launch', 'campaign_pause', 'campaign_budget_update'), write_enabled=True, human_verification_required=True),
            ChannelCapabilityDescriptor('google_ads.reporting', ('campaign_report_read',), write_enabled=False, human_verification_required=False),
        ),
    )


class TiktokAdsProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.CAMPAIGN_ADS
    adapter_key = 'campaign_ads.tiktok'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('tiktok_ads.campaigns', ('campaign_launch', 'campaign_pause', 'campaign_budget_update'), write_enabled=True, human_verification_required=True),
            ChannelCapabilityDescriptor('tiktok_ads.reporting', ('campaign_report_read',), write_enabled=False, human_verification_required=False),
        ),
    )
