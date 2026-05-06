from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.ads_library_family import AdsLibraryFamilyConnector


@dataclass
class GoogleAdsPreviewConnector(AdsLibraryFamilyConnector):
    connector_name: str = 'google_ads_preview'
    connector_id: str = 'google_ads_preview'
    provider_key: str = 'google'
    version: str = 'v1'


__all__ = ['GoogleAdsPreviewConnector']
