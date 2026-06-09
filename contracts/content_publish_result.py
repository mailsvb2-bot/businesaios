from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContentPublishResult:
    content_id: str = ''
    status: str = ''
    url: str = ''
