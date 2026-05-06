from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ConnectedAdsAccount:
    tenant_id: str
    platform: str
    account_id: str
