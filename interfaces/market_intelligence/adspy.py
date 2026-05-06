from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.ads_spy_family import AdsSpyFamilyConnector


@dataclass
class AdspyConnector(AdsSpyFamilyConnector):
    connector_name: str = 'adspy'
    connector_id: str = 'adspy'
    provider_key: str = 'adspy'
    version: str = 'v1'


__all__ = ['AdspyConnector']
