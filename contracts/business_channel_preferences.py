from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BusinessChannelPreferences:
    ads_enabled: bool = False
    seo_enabled: bool = False
    platforms_enabled: bool = False
