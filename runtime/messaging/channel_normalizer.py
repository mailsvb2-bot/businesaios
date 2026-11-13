from __future__ import annotations

from runtime.messaging.channel_aliases import ALIASES
from runtime.messaging.channel_types import ALL_CHANNELS, CHANNEL_TELEGRAM


def normalize_channel(value: str | None) -> str:
    raw = str(value or CHANNEL_TELEGRAM).strip().lower().replace("-", "_")
    out = ALIASES.get(raw, raw)
    if out not in ALL_CHANNELS:
        raise ValueError(f"UNKNOWN_CHANNEL:{out}")
    return out


def split_command(text: str) -> tuple[str, str]:
    stripped = str(text or "").strip()
    if not stripped.startswith("/"):
        return "", stripped
    head, _, tail = stripped.partition(" ")
    return head.split("@", 1)[0].lower(), tail.strip()
