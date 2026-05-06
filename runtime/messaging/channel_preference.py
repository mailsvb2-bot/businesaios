from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.messaging.channel_normalizer import normalize_channel


def _uniq(values: list[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return tuple(out)


@dataclass(frozen=True)
class ChannelPreference:
    primary: str
    enabled: tuple[str, ...]
    verified: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        primary = normalize_channel(self.primary)
        normalized_enabled = _uniq([normalize_channel(primary), *[normalize_channel(item) for item in self.enabled]])
        normalized_verified = tuple(item for item in _uniq([normalize_channel(item) for item in self.verified]) if item in normalized_enabled)
        object.__setattr__(self, "primary", primary)
        object.__setattr__(self, "enabled", normalized_enabled)
        object.__setattr__(self, "verified", normalized_verified)

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "ChannelPreference":
        data = dict(value or {})
        primary = str(data.get("primary") or "telegram")
        enabled_raw = data.get("enabled")
        verified_raw = data.get("verified")
        enabled = tuple(enabled_raw) if isinstance(enabled_raw, (list, tuple)) else (primary,)
        verified = tuple(verified_raw) if isinstance(verified_raw, (list, tuple)) else ()
        return cls(primary=primary, enabled=enabled, verified=verified)
