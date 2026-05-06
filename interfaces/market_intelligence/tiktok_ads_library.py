from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.ads_library_family import AdsLibraryFamilyConnector


@dataclass
class TiktokAdsLibraryConnector(AdsLibraryFamilyConnector):
    connector_name: str = 'tiktok_ads_library'
    connector_id: str = 'tiktok_ads_library'
    provider_key: str = 'tiktok'
    version: str = 'v1'


__all__ = ['TiktokAdsLibraryConnector']
