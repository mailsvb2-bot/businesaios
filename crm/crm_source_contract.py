from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrmSource:
    source_key: str
    display_name: str
    channel: str
