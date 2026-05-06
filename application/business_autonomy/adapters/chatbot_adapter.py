from __future__ import annotations

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import ChannelCapabilityDescriptor, ChannelKind


class ChatbotChannelAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.CHATBOT
    adapter_key = "chatbot.default"
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor("chat.send", ('message_send',), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor("chat.read", ('message_read',), write_enabled=False, human_verification_required=False),
        ),
    )
