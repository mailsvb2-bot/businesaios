from __future__ import annotations

from interfaces.market_intelligence.app_store_family import AppStoreFamilyConnector


CANON_APPLE_APP_STORE_CONNECTOR = True


class AppleAppStoreConnector(AppStoreFamilyConnector):
    connector_name = 'apple_app_store'
    connector_id = 'apple_app_store'
    provider_key = 'apple_app_store'


__all__ = ['CANON_APPLE_APP_STORE_CONNECTOR', 'AppleAppStoreConnector']
