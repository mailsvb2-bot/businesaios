from __future__ import annotations

from pathlib import Path

from interfaces.crm import CONNECTORS as CRM_CONNECTORS
from interfaces.crm import HubspotConnector
from interfaces.platforms import CONNECTORS as PLATFORM_CONNECTORS
from interfaces.platforms import GoogleMapsConnector
from interfaces.website import CONNECTORS as WEBSITE_CONNECTORS
from interfaces.website import SiteConnector

ROOT = Path(__file__).resolve().parents[2]


def test_only_honest_connector_surfaces_remain() -> None:
    assert HubspotConnector.connector_name == "hubspot_connector"
    assert GoogleMapsConnector.connector_name == "google_maps_connector"
    assert SiteConnector.connector_name == "site_connector"


def test_removed_connector_modules_do_not_exist_anymore() -> None:
    removed = [
        "interfaces/crm/amo_connector.py",
        "interfaces/crm/bitrix_connector.py",
        "interfaces/crm/generic_crm_connector.py",
        "interfaces/crm/pipedrive_connector.py",
        "interfaces/crm/salesforce_connector.py",
        "interfaces/platforms/amazon_connector.py",
        "interfaces/platforms/avito_connector.py",
        "interfaces/platforms/craigslist_connector.py",
        "interfaces/platforms/etsy_connector.py",
        "interfaces/platforms/fiverr_connector.py",
        "interfaces/platforms/upwork_connector.py",
        "interfaces/platforms/yelp_connector.py",
        "interfaces/website/analytics_connector.py",
        "interfaces/website/cms_shopify_connector.py",
        "interfaces/website/cms_webflow_connector.py",
        "interfaces/website/cms_wordpress_connector.py",
        "interfaces/website/form_events_connector.py",
        "interfaces/crm/catalog.py",
        "interfaces/platforms/catalog.py",
        "interfaces/website/catalog.py",
    ]
    for rel in removed:
        assert not (ROOT / rel).exists(), rel


def test_registry_entries_are_capability_aware_and_honest() -> None:
    assert CRM_CONNECTORS["hubspot"]["status"] == "implemented"
    assert CRM_CONNECTORS["hubspot"]["production_ready"] is False
    assert CRM_CONNECTORS["amo"]["status"] == "not_implemented"
    assert CRM_CONNECTORS["amo"]["write"] is False

    assert PLATFORM_CONNECTORS["google_maps"]["status"] == "implemented"
    assert PLATFORM_CONNECTORS["google_maps"]["production_ready"] is False
    assert PLATFORM_CONNECTORS["amazon"]["status"] == "not_implemented"

    assert WEBSITE_CONNECTORS["site"]["status"] == "implemented"
    assert WEBSITE_CONNECTORS["site"]["action_types"] == ["create_landing_page", "publish_service_page"]
    assert WEBSITE_CONNECTORS["cms_wordpress"]["status"] == "not_implemented"

    for registry in (CRM_CONNECTORS, PLATFORM_CONNECTORS, WEBSITE_CONNECTORS):
        for entry in registry.values():
            assert set(entry) == {
                "name",
                "status",
                "implemented",
                "stub",
                "read",
                "write",
                "verify",
                "supports_dry_run",
                "supports_idempotency",
                "production_ready",
                "reversible",
                "requires_human_approval",
                "action_types",
                "truth_layer",
            }
            assert entry["truth_layer"]["write_enabled"] is bool(entry["write"])
            assert entry["truth_layer"]["verify_enabled"] is bool(entry["verify"])
