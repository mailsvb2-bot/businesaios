from __future__ import annotations

from typing import Any

from runtime.messaging.channel_preference import ChannelPreference

SETTING_KEY = "messaging:channel_preference"


def canonical_channel_preference_value(*, primary: str, enabled: list[str] | tuple[str, ...], verified: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
    pref = ChannelPreference(primary=primary, enabled=tuple(enabled), verified=tuple(verified or ()))
    return {
        "primary": pref.primary,
        "enabled": list(pref.enabled),
        "verified": list(pref.verified),
    }
