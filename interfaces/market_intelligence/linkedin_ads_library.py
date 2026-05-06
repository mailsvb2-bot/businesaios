from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.ads_library_family import AdsLibraryFamilyConnector


@dataclass
class LinkedinAdsLibraryConnector(AdsLibraryFamilyConnector):
    connector_name: str = 'linkedin_ads_library'
    connector_id: str = 'linkedin_ads_library'
    provider_key: str = 'linkedin'
    version: str = 'v1'


__all__ = ['LinkedinAdsLibraryConnector']
