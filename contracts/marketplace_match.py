from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketplaceMatch:
    match_id: str = ''
    business_id: str = ''
    client_id: str = ''
