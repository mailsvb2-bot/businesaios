from __future__ import annotations

from dataclasses import dataclass

from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging.channel_preference import ChannelPreference
from runtime.messaging_policy.delivery_snapshot import DeliverySnapshot
from runtime.messaging_policy.unanswered_snapshot import UnansweredSnapshot


def _normalize_optional(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return normalize_channel(text)


def _normalize_many(value) -> tuple[str, ...]:
    if not isinstance(value, list | tuple | set):
        return ()
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        out.append(normalize_channel(text))
    return tuple(dict.fromkeys(out))


@dataclass(frozen=True)
class PolicyRequest:
    preference: ChannelPreference
    preferred_channel: str | None = None
    fallback_channels: tuple[str, ...] = ()
    verified_only: bool = False
    critical: bool = True
    attempt_index: int = 0
    unanswered_threshold_s: int = 0
    delivery_snapshot: DeliverySnapshot = DeliverySnapshot()
    unanswered_snapshot: UnansweredSnapshot = UnansweredSnapshot()

    def __post_init__(self) -> None:
        object.__setattr__(self, "preferred_channel", _normalize_optional(self.preferred_channel))
        object.__setattr__(self, "fallback_channels", _normalize_many(self.fallback_channels))
        object.__setattr__(self, "verified_only", bool(self.verified_only))
        object.__setattr__(self, "critical", bool(self.critical))
        object.__setattr__(self, "attempt_index", max(0, int(self.attempt_index or 0)))
        object.__setattr__(self, "unanswered_threshold_s", max(0, int(self.unanswered_threshold_s or 0)))
