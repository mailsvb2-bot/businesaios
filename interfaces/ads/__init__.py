"""Honest Ads connector interfaces.

This package exports the single implemented external connector surface and
the shared contracts used by runtime wiring.
"""

from .base import (
    AdsConnector,
    AdsReadConnector,
    AdsWriteConnector,
    AdsConnectorError,
    AdsObjectRef,
    AdsPlatform,
    Campaign,
    ConnectedAccount,
    MetricPoint,
    OAuthAuthorizeURL,
)
from .google_ads_connector import GoogleAdsConnector, GoogleAdsConfig
from .read_service import AdsReadService
from .registry import AdsConnectorRegistry, CONNECTORS
from .token_store_adapter import AdsTokenStoreAdapter

__all__ = [
    "AdsConnector",
    "AdsConnectorError",
    "AdsConnectorRegistry",
    "AdsObjectRef",
    "AdsPlatform",
    "AdsReadConnector",
    "AdsReadService",
    "AdsTokenStoreAdapter",
    "AdsWriteConnector",
    "CONNECTORS",
    "Campaign",
    "ConnectedAccount",
    "GoogleAdsConfig",
    "GoogleAdsConnector",
    "MetricPoint",
    "OAuthAuthorizeURL",
]
