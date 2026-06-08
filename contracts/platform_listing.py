from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformListing:
    listing_id: str = ''
    platform: str = ''
    status: str = ''
