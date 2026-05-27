from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CampaignState:
    campaign_id: str = ''
    status: str = ''
    last_sync_at: object | None = None
