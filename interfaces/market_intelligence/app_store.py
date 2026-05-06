from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.app_store_family import AppStoreFamilyConnector


@dataclass
class AppStoreConnector(AppStoreFamilyConnector):
    connector_name: str = 'app_store'
    connector_id: str = 'app_store'
    provider_key: str = 'apple'
    version: str = 'v1'


__all__ = ['AppStoreConnector']
