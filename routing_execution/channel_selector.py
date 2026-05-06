from __future__ import annotations

from config.execution_contract import DEFAULT_DELIVERY_CHANNEL, DEFAULT_MANUAL_REVIEW_CHANNEL


class ChannelSelector:
    def choose(self, *, request, decision, available_channels: tuple[str, ...] = ()) -> str:
        del request
        if getattr(decision, 'requires_manual_review', False):
            return DEFAULT_MANUAL_REVIEW_CHANNEL
        trace = getattr(decision, 'trace', {}) or {}
        preferred = str(trace.get('delivery_channel') or '')
        allowed = tuple(str(channel) for channel in available_channels)
        if not allowed:
            return preferred or DEFAULT_DELIVERY_CHANNEL
        if preferred and preferred in allowed:
            return preferred
        if DEFAULT_DELIVERY_CHANNEL in allowed:
            return DEFAULT_DELIVERY_CHANNEL
        return str(allowed[0])
