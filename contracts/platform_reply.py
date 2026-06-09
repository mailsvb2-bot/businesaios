from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformReply:
    reply_id: str = ''
    platform: str = ''
    message: str = ''
