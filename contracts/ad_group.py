from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AdGroup:
    ad_group_id: str = ''
    campaign_id: str = ''
    audience_name: str = ''
