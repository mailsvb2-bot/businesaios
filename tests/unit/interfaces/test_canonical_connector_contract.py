from __future__ import annotations

from interfaces.ads.google_ads_connector import GoogleAdsConnector
from interfaces.common.base_connector import BaseConnector
from interfaces.common.canonical_connector_contract import canonical_connector_contract


class DummyConnector(BaseConnector):
    pass


def test_canonical_connector_contract_marks_placeholder_honestly() -> None:
    contract = canonical_connector_contract(
        connector_name='site_connector',
        maturity='placeholder',
        configured=False,
        mode='stub',
        capabilities={'write': False, 'verify': False},
    )
    assert contract['is_placeholder'] is True
    assert contract['routing_readiness'] == 'placeholder'


def test_base_connector_health_exposes_capability_contract() -> None:
    health = DummyConnector().health()
    assert 'capability_contract' in health.metadata
    assert health.metadata['capability_contract']['maturity'] == 'placeholder'


def test_capability_shell_connector_exposes_routing_readiness() -> None:
    health = GoogleAdsConnector().health()
    assert health.metadata['capability_contract']['maturity'] == 'capability_shell'
    assert health.metadata['capability_contract']['routing_readiness'] == 'shell_only'
