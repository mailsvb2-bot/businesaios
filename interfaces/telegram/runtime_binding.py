from __future__ import annotations

from interfaces.messaging_runtime.channel_factory import build_channel_binding


def build_binding(*, sender=None):
    return build_channel_binding(channel='telegram', sender=sender)
