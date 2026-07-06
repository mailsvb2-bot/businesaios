from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging.settings import canonical_channel_preference_value


def _parse_channels(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        parts = [item.strip() for item in value.split(",")]
    elif isinstance(value, Iterable):
        parts = [str(item).strip() for item in value]
    else:
        parts = []

    out: list[str] = []
    for item in parts:
        if not item:
            continue
        out.append(normalize_channel(item))
    return tuple(dict.fromkeys(out))


def parse_preference_form(payload: Mapping[str, Any]) -> dict[str, Any]:
    p = dict(payload or {})
    primary = normalize_channel(str(p.get("primary") or "telegram"))
    enabled = _parse_channels(p.get("enabled") or ())
    verified = _parse_channels(p.get("verified") or ())
    return canonical_channel_preference_value(
        primary=primary,
        enabled=enabled,
        verified=verified,
    )
