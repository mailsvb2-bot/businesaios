from __future__ import annotations

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import ChannelCapabilityDescriptor, ChannelKind

CANON_WEBSITE_PRODUCTION_ADAPTERS = True


class WebflowProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.WEBSITE
    adapter_key = 'website.webflow'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('webflow.content', ('page_publish', 'cms_item_publish'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('webflow.site', ('webhook_receive', 'site_config_read'), write_enabled=False, human_verification_required=False),
        ),
    )


class WordpressProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.WEBSITE
    adapter_key = 'website.wordpress'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('wordpress.content', ('page_publish', 'post_publish'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('wordpress.site', ('webhook_receive', 'site_config_read'), write_enabled=False, human_verification_required=False),
        ),
    )
