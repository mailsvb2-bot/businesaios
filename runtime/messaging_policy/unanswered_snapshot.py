from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from runtime.messaging.channel_normalizer import normalize_channel


@dataclass(frozen=True)
class UnansweredSnapshot:
    current_channel: str | None = None
    seconds_since_last_user_reply: int = 0

    def __post_init__(self) -> None:
        current = self.current_channel
        if isinstance(current, str) and current.strip():
            object.__setattr__(self, "current_channel", normalize_channel(current))
        else:
            object.__setattr__(self, "current_channel", None)
        object.__setattr__(self, "seconds_since_last_user_reply", int(self.seconds_since_last_user_reply or 0))

    @staticmethod
    def from_mapping(value: Mapping[str, Any] | None) -> UnansweredSnapshot:
        if not isinstance(value, Mapping):
            return UnansweredSnapshot()
        return UnansweredSnapshot(
            current_channel=value.get("current_channel"),
            seconds_since_last_user_reply=int(value.get("seconds_since_last_user_reply") or 0),
        )
