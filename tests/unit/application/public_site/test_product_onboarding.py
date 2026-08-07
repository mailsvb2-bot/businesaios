from __future__ import annotations

from application.public_site.cta_intake import CTALandingIntakeService, public_integration_marketplace
from entrypoints.api.public_surface_route_specs import _ROUTE_SPECS
from security.access_policy import SecurityAction


def test_public_integration_marketplace_never_claims_live_write_support() -> None:
    rows = public_integration_marketplace()

    assert rows
    assert any(row["provider_key"] == "hubspot" for row in rows)
    assert all(row["write_supported"] is False for row in rows)
    assert all("availability_label" in row for row in rows)
    assert all("credential_labels" in row for row in rows)
    assert all(row["selectable"] is row["read_supported"] for row in rows)


def test_integration_marketplace_route_is_public_read_only() -> None:
    spec = _ROUTE_SPECS["/public-site/integrations"]

    assert spec.action is SecurityAction.READ
    assert "public" in spec.tags
    assert "internal" not in spec.tags


def test_self_service_onboarding_persists_business_plan(tmp_path) -> None:
    service = CTALandingIntakeService(
        storage_path=str(tmp_path / "intakes.jsonl"),
        app_base_url="https://app.example.test",
    )

    created = service.submit(
        payload={
            "email": "owner@example.test",
            "business_name": "North Star Studio",
            "website": "https://north-star.example.test",
            "industry": "services",
            "city": "Warsaw",
            "business_model": "services",
            "goal": "retention",
            "selected_providers": ["hubspot", "telegram_bot", "unknown", "hubspot"],
            "autonomy_mode": "assistant",
        }
    )

    assert created.business_profile["name"] == "North Star Studio"
    assert created.business_profile["email"] == "owner@example.test"
    assert created.business_profile["website"] == "https://north-star.example.test"
    assert created.business_profile["industry"] == "services"
    assert created.business_profile["city"] == "Warsaw"
    assert created.business_profile["business_model"] == "services"
    assert created.business_profile["goal"] == "retention"
    assert created.selected_providers == ("hubspot", "telegram_bot")
    assert created.autonomy_mode == "assistant"
    assert created.onboarding_status == "advisory_intake_created"
    assert created.onboarding_progress["percent"] == 67
    assert created.first_value_preview["requires_real_sync"] is True
    assert created.first_value_preview["contains_estimated_financial_claims"] is False
    assert all(item["write_actions_enabled"] is False for item in created.integration_plan)

    loaded = service.get_status(intake_id=created.intake_id)

    assert loaded.found is True
    assert loaded.business_profile == created.business_profile
    assert loaded.selected_providers == created.selected_providers
    assert loaded.integration_plan == created.integration_plan
    assert loaded.autonomy_mode == "assistant"
    assert loaded.first_value_preview == created.first_value_preview


def test_unknown_autonomy_mode_fails_safe_to_advisor(tmp_path) -> None:
    service = CTALandingIntakeService(storage_path=str(tmp_path / "intakes.jsonl"))

    created = service.submit(
        payload={
            "email": "owner@example.test",
            "business_name": "Safe Business",
            "goal": "growth",
            "selected_providers": ["hubspot"],
            "autonomy_mode": "unlimited",
        }
    )

    assert created.autonomy_mode == "advisor"
    assert created.user_functionality["autonomy_mode_label"] == "Советник"
    assert "provider_write_actions" in created.user_functionality["blocked_until_approval"]
