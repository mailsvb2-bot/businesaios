from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.ads_library_family import AdsLibraryFamilyConnector


@dataclass
class FacebookAdLibraryConnector(AdsLibraryFamilyConnector):
    connector_name: str = 'facebook_ad_library'
    connector_id: str = 'facebook_ad_library'
    provider_key: str = 'meta'
    version: str = 'v1'


__all__ = ['FacebookAdLibraryConnector']
