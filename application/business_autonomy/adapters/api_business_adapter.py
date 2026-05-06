from __future__ import annotations

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import ChannelCapabilityDescriptor, ChannelKind


class ApiBusinessChannelAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.API_BUSINESS
    adapter_key = "api.default"
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor("api.invoke", ('api_call',), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor("api.read_model", ('api_read',), write_enabled=False, human_verification_required=False),
        ),
    )
