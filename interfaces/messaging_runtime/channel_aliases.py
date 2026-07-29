"""Interface compatibility surface for canonical runtime channel names."""

from __future__ import annotations

from runtime.messaging.channel_normalizer import normalize_channel

CANON_MESSAGING_RUNTIME_CHANNEL_NORMALIZER_DELEGATE = True


def canonical_channel_name(channel: str) -> str:
    """Normalize legacy/provider spellings through the sole runtime owner."""

    return normalize_channel(channel)


__all__ = [
    "CANON_MESSAGING_RUNTIME_CHANNEL_NORMALIZER_DELEGATE",
    "canonical_channel_name",
]
