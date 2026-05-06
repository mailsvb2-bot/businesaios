from __future__ import annotations

from guardrails._shared import GuardCheckResult, _as_text, _channels, _payload_view


class UnsafeChannelGuard:
    def check(self, payload: dict) -> tuple[bool, str]:
        body = _payload_view(payload)
        channel = _as_text(body.get('channel')).lower()
        if not channel:
            return GuardCheckResult(True, 'channel_not_specified').as_tuple()
        allowed_channels = _channels(body)
        if allowed_channels and channel not in allowed_channels:
            return GuardCheckResult(False, 'unsafe_channel').as_tuple()
        return GuardCheckResult(True, 'channel_allowed').as_tuple()
