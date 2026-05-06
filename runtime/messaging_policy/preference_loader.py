from __future__ import annotations

from runtime.messaging.channel_preference import ChannelPreference
from runtime.messaging.settings import SETTING_KEY


def load_channel_preference(*, settings_gateway, tenant_id: str) -> ChannelPreference:
    if settings_gateway is None:
        return ChannelPreference(primary="telegram", enabled=("telegram",), verified=())

    value = settings_gateway.get_value(
        tenant_id=str(tenant_id),
        key=SETTING_KEY,
    )
    return ChannelPreference.from_mapping(value if isinstance(value, dict) else None)
