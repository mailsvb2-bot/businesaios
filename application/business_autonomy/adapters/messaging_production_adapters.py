from __future__ import annotations

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import ChannelCapabilityDescriptor, ChannelKind

CANON_MESSAGING_PRODUCTION_ADAPTERS = True


class WhatsAppProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.CHATBOT
    adapter_key = 'chatbot.whatsapp'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('whatsapp.send', ('message_send', 'template_send'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('whatsapp.read', ('message_read', 'contact_profile_read'), write_enabled=False, human_verification_required=False),
        ),
    )


class EmailProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.CHATBOT
    adapter_key = 'chatbot.email'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('email.delivery', ('message_send', 'campaign_send'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('email.inbox', ('message_read', 'thread_sync'), write_enabled=False, human_verification_required=False),
        ),
    )


class SmsProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.CHATBOT
    adapter_key = 'chatbot.sms'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('sms.delivery', ('message_send',), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('sms.status', ('delivery_status_read',), write_enabled=False, human_verification_required=False),
        ),
    )
