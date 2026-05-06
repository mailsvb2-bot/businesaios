from __future__ import annotations

from contracts.platforms.market_intelligence_provider_catalog import PROVIDER_CATALOG
from interfaces.market_intelligence.amazon import AmazonConnector
from interfaces.market_intelligence.facebook_ad_library import FacebookAdLibraryConnector
from interfaces.market_intelligence.provider_factory import build_default_provider_client, provider_supported
from runtime._internal.market_intelligence.provider_runtime import ProviderRuntimeFactory


def test_runtime_factory_covers_all_catalog_providers() -> None:
    factory = ProviderRuntimeFactory()
    missing = [provider for provider in PROVIDER_CATALOG if not factory.supports_provider(provider)]
    assert missing == []


def test_default_provider_factory_wires_marketplace_connector() -> None:
    connector = AmazonConnector()
    assert connector.provider_client is not None
    assert connector.session.configured is True
    assert connector.connector_maturity().value == 'real'


def test_default_provider_factory_wires_alias_based_connector() -> None:
    connector = FacebookAdLibraryConnector()
    assert connector.provider_client is not None
    assert connector.session.configured is True
    assert connector.provider_key == 'meta'
    assert provider_supported('meta') is True
    assert build_default_provider_client('meta') is not None
