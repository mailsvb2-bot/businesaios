from __future__ import annotations

from dataclasses import dataclass

from runtime.messaging.channel_normalizer import normalize_channel


@dataclass(frozen=True)
class ChannelHealth:
    channel: str
    healthy: bool = True
    health_score: float = 1.0
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "channel", normalize_channel(self.channel))
        object.__setattr__(self, "healthy", bool(self.healthy))
        object.__setattr__(self, "health_score", max(0.0, min(1.0, float(self.health_score))))
        object.__setattr__(self, "reason", str(self.reason or ""))
