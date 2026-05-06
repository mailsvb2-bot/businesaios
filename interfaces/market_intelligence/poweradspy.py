from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.ads_spy_family import AdsSpyFamilyConnector


@dataclass
class PoweradspyConnector(AdsSpyFamilyConnector):
    connector_name: str = 'poweradspy'
    connector_id: str = 'poweradspy'
    provider_key: str = 'poweradspy'
    version: str = 'v1'


__all__ = ['PoweradspyConnector']
