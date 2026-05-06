from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.ads_spy_family import AdsSpyFamilyConnector


@dataclass
class BigspyConnector(AdsSpyFamilyConnector):
    connector_name: str = 'bigspy'
    connector_id: str = 'bigspy'
    provider_key: str = 'bigspy'
    version: str = 'v1'


__all__ = ['BigspyConnector']
