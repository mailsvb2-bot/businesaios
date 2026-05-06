from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.ads_library_family import AdsLibraryFamilyConnector


@dataclass
class PinterestAdsLibraryConnector(AdsLibraryFamilyConnector):
    connector_name: str = 'pinterest_ads_library'
    connector_id: str = 'pinterest_ads_library'
    provider_key: str = 'pinterest'
    version: str = 'v1'


__all__ = ['PinterestAdsLibraryConnector']
