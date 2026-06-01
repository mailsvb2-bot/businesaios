from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlatformReply:
    reply_id: str = ''
    platform: str = ''
    message: str = ''
