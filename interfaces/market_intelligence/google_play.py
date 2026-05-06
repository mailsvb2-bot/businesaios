from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.app_store_family import AppStoreFamilyConnector


@dataclass
class GooglePlayConnector(AppStoreFamilyConnector):
    connector_name: str = 'google_play'
    connector_id: str = 'google_play'
    provider_key: str = 'google'
    version: str = 'v1'


__all__ = ['GooglePlayConnector']
