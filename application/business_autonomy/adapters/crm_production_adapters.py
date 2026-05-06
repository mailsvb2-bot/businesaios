from __future__ import annotations

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import ChannelCapabilityDescriptor, ChannelKind

CANON_CRM_PRODUCTION_ADAPTERS = True


class CallTrackingProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.BACKOFFICE
    adapter_key = 'backoffice.call_tracking'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('call_tracking.calls', ('call_sync', 'attribution_sync'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('call_tracking.reports', ('report_read',), write_enabled=False, human_verification_required=False),
        ),
    )


class HubSpotProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.BACKOFFICE
    adapter_key = 'backoffice.hubspot'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('hubspot.crm', ('contact_sync', 'deal_sync', 'task_create'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('hubspot.webhooks', ('webhook_receive',), write_enabled=False, human_verification_required=False),
        ),
    )
