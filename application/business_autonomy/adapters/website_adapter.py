from __future__ import annotations

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import ChannelCapabilityDescriptor, ChannelKind


class WebsiteChannelAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.WEBSITE
    adapter_key = "website.default"
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor("web.content", ('content_publish', 'content_update'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor("web.analytics", ('web_analytics_pull',), write_enabled=False, human_verification_required=False),
        ),
    )
