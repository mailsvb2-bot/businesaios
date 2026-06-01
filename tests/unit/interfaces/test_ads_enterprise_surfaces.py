from __future__ import annotations

import pytest

from connectors.platform.ads.registry import AdsConnectorRegistry as PlatformAdsRegistry
from connectors.platform.ads.sqlite_token_store import SqliteAdsTokenStore
from connectors.platform.ads.token_store import OAuthToken
from interfaces.ads.capabilities import AdsCapabilities
from interfaces.ads.connector_availability_guard import assert_live_write_allowed, ensure_demo_registry_truth
from interfaces.ads.google_ads_connector import GoogleAdsConnector
from interfaces.ads.registry import CONNECTORS, AdsConnectorRegistry


def test_ads_capabilities_bridge_to_common_connector_contract() -> None:
    caps = AdsCapabilities(
        read_inventory=True,
        read_metrics=True,
        write_campaigns=True,
        verify_writes=True,
        production_ready=True,
        operation_names=('sync',),
    )
    common = caps.to_connector_capabilities()
    assert common.write is True
    assert common.verify is True
    assert common.metadata['production_ready'] is True


def test_interface_ads_registry_blocks_duplicate_registration() -> None:
    registry = AdsConnectorRegistry()
    connector = GoogleAdsConnector()
    registry.register(connector)
    with pytest.raises(KeyError):
        registry.register(connector)


def test_platform_ads_registry_exposes_capability_snapshot() -> None:
    registry = PlatformAdsRegistry()
    connector = GoogleAdsConnector()
    registry.register(connector)
    snapshot = registry.snapshot()
    assert snapshot[0]['platform'] == 'google_ads'
    assert snapshot[0]['capabilities']['supports_read'] is True


def test_sqlite_token_store_validates_and_round_trips(tmp_path) -> None:
    store = SqliteAdsTokenStore(tmp_path / 'tokens.db')
    token = OAuthToken(access_token='abc')
    store.put(tenant_id='t1', platform='google_ads', account_id='a1', token=token)
    loaded = store.get(tenant_id='t1', platform='google_ads', account_id='a1')
    assert loaded is not None
    assert loaded.access_token == 'abc'
    assert store.snapshot()['backend'] == 'sqlite'


def test_stub_guard_rejects_live_write_for_stub() -> None:
    with pytest.raises(RuntimeError):
        assert_live_write_allowed(platform='meta_ads', metadata={'connector_mode': 'stub', 'production_ready': False})
    ensure_demo_registry_truth(platform='meta_ads', entry=CONNECTORS['meta_ads'])
