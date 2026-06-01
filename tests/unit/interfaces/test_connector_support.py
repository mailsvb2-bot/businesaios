from __future__ import annotations

from interfaces.ads.google_ads_connector import GoogleAdsConnector
from interfaces.common.base_connector import BaseConnector


class DummyConnector(BaseConnector):
    def _execute_configured(self, operation, payload):
        return super()._execute_configured(operation, payload)


def test_base_connector_rejects_non_mapping_payload() -> None:
    conn = DummyConnector()
    result = conn.execute("sync", payload=["bad"])
    assert result.code == "invalid_payload"


def test_base_connector_exposes_stub_mode_in_health() -> None:
    conn = DummyConnector()
    health = conn.health()
    assert health.metadata["mode"] == "stub"
    assert health.metadata["maturity"] == "placeholder"
    assert health.metadata["configured"] is False
    assert health.metadata["maturity"] == "placeholder"
    assert health.metadata["supports_write"] is False
    assert health.metadata["supports_verify"] is False


def test_google_ads_execute_rejects_non_mapping_payload() -> None:
    conn = GoogleAdsConnector()
    result = conn.execute("preview", payload=["bad"])
    assert result.code == "invalid_payload"


def test_google_ads_health_exposes_mode() -> None:
    conn = GoogleAdsConnector()
    health = conn.health()
    assert health.metadata["mode"] == "stub"
    assert health.metadata["maturity"] == "capability_shell"


def test_placeholder_connectors_are_explicit_about_maturity() -> None:
    from interfaces.communications.sms_connector import SmsConnector
    from interfaces.crm.hubspot_connector import HubspotConnector
    from interfaces.platforms.google_maps_connector import GoogleMapsConnector
    from interfaces.reviews.google_reviews_connector import GoogleReviewsConnector
    from interfaces.website.site_connector import SiteConnector

    for connector in (
        HubspotConnector(),
        GoogleMapsConnector(),
        GoogleReviewsConnector(),
        SiteConnector(),
        SmsConnector(),
    ):
        health = connector.health()
        assert health.metadata["maturity"] == "placeholder"
        assert health.metadata["supports_write"] is False
        assert health.metadata["supports_verify"] is False
        assert connector.capabilities()["metadata"]["maturity"] == "placeholder"


def test_capability_shell_connectors_report_maturity_honestly() -> None:
    from interfaces.common.auth_session import AuthSession
    from interfaces.communications.email_connector import EmailConnector

    ads = GoogleAdsConnector()
    email = EmailConnector(session=AuthSession(configured=True))

    assert ads.health().metadata["maturity"] == "capability_shell"
    assert email.health().metadata["maturity"] == "capability_shell"
    assert email.capabilities()["metadata"]["maturity"] == "capability_shell"
