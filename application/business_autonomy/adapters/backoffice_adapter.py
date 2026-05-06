from __future__ import annotations

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import ChannelCapabilityDescriptor, ChannelKind


class BackofficeChannelAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.BACKOFFICE
    adapter_key = "backoffice.default"
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor("backoffice.tasks", ('task_create', 'task_assign'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor("backoffice.read", ('report_read',), write_enabled=False, human_verification_required=False),
        ),
    )
