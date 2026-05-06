from __future__ import annotations

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import ChannelCapabilityDescriptor, ChannelKind


class CommerceChannelAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.COMMERCE
    adapter_key = "commerce.default"
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor("commerce.catalog", ('catalog_sync',), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor("commerce.orders", ('order_sync', 'refund_request'), write_enabled=True, human_verification_required=True),
        ),
    )
