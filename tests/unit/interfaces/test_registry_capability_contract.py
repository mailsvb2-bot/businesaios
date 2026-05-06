from __future__ import annotations

from interfaces.ads import CONNECTORS as ADS_CONNECTORS
from interfaces.common.registry_capability_contract import RegistryCapabilityEntry, build_registry_entry
from interfaces.crm import CONNECTORS as CRM_CONNECTORS
from interfaces.platforms import CONNECTORS as PLATFORM_CONNECTORS
from interfaces.reviews import CONNECTORS as REVIEW_CONNECTORS
from interfaces.website import CONNECTORS as WEBSITE_CONNECTORS


def test_registry_capability_entry_serializes_expected_shape() -> None:
    entry = RegistryCapabilityEntry(
        name="demo",
        status="implemented",
        read=True,
        write=False,
        verify=True,
        supports_dry_run=True,
        supports_idempotency=False,
        production_ready=False,
        action_types=("alpha", "beta"),
    ).as_dict()
    assert entry == {
        "name": "demo",
        "status": "implemented",
        "implemented": True,
        "stub": False,
        "read": True,
        "write": False,
        "verify": True,
        "supports_dry_run": True,
        "supports_idempotency": False,
        "production_ready": False,
        "reversible": False,
        "requires_human_approval": True,
        "action_types": ["alpha", "beta"],
        "truth_layer": {
            "implemented": True,
            "stub": False,
            "write_enabled": False,
            "verify_enabled": True,
            "dry_run_enabled": True,
            "idempotent": False,
            "reversible": False,
            "requires_human_approval": True,
        },
    }


def test_registry_capability_build_helper_returns_honest_entries() -> None:
    entry = build_registry_entry(name="demo", status="not_implemented")
    assert entry["status"] == "not_implemented"
    assert entry["production_ready"] is False
    assert entry["action_types"] == []


def test_registry_maps_publish_capability_surface() -> None:
    assert ADS_CONNECTORS["google_ads"]["status"] == "implemented"
    assert ADS_CONNECTORS["google_ads"]["production_ready"] is False
    assert CRM_CONNECTORS["hubspot"]["status"] == "implemented"
    assert PLATFORM_CONNECTORS["google_maps"]["status"] == "implemented"
    assert REVIEW_CONNECTORS["google_reviews"]["action_types"] == ["request_review"]
    assert WEBSITE_CONNECTORS["site"]["action_types"] == ["create_landing_page", "publish_service_page"]
