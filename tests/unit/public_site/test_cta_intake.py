from __future__ import annotations

import json

from application.public_site.cta_intake import CTALandingIntakeService, public_integration_marketplace


def test_cta_intake_records_row_and_returns_ui_url(tmp_path):
    path = tmp_path / "pilot_applications.jsonl"
    result = CTALandingIntakeService(storage_path=str(path), app_base_url="https://app.businessaios.ru").submit(payload={"email": "test@example.com", "intent": "demo"})
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert result.intake_id.startswith("cta-") and result.outcome == "intake_recorded" and result.app_url.endswith(result.intake_id)
    assert row["intake_id"] == result.intake_id and row["source"] == "public_landing_cta"


def test_cta_intake_status_lookup(tmp_path):
    service = CTALandingIntakeService(storage_path=str(tmp_path / "pilot_applications.jsonl"))
    result = service.submit(payload={"email": "a@b.c"})
    found, missing = service.get_status(intake_id=result.intake_id), service.get_status(intake_id="cta-missing")
    assert found.found is True and found.outcome == "intake_recorded"
    assert missing.found is False and missing.outcome == "not_found"


def test_self_service_plan_is_truthful_persistent_and_fail_safe(tmp_path):
    assert all(row["write_supported"] is False for row in public_integration_marketplace())
    service = CTALandingIntakeService(storage_path=str(tmp_path / "cta.jsonl"))
    result = service.submit(payload={"email": "owner@example.test", "business_name": "North Star", "industry": "services", "goal": "retention", "selected_providers": ["hubspot", "telegram_bot", "unknown", "hubspot"], "autonomy_mode": "unlimited"})
    assert result.selected_providers == ("hubspot", "telegram_bot") and result.autonomy_mode == "advisor"
    assert result.user_functionality["autonomy_mode_label"] == "Советник" and result.onboarding_progress["percent"] == 67
    assert result.first_value_preview["requires_real_sync"] is True and result.first_value_preview["contains_estimated_financial_claims"] is False
    assert all(item["write_actions_enabled"] is False for item in result.integration_plan)
    restored = service.get_status(intake_id=result.intake_id)
    assert (restored.business_profile, restored.selected_providers, restored.integration_plan) == (result.business_profile, result.selected_providers, result.integration_plan)


def test_native_messaging_connection_modes_are_exposed_truthfully() -> None:
    rows = {row["provider_key"]: row for row in public_integration_marketplace()}
    assert rows["vk_messaging"]["connection_mode"] == "native_vk_callback_or_provider_webhook_bridge"
    assert rows["max_messaging"]["connection_mode"] == "native_max_api_or_provider_webhook_bridge"
    assert rows["slack_messaging"]["connection_mode"] == "native_slack_events_or_provider_webhook_bridge"
    assert rows["discord_messaging"]["connection_mode"] == "native_discord_http_or_provider_webhook_bridge"
    assert rows["slack_messaging"]["credential_labels"] == ["Slack Signing Secret"]
    assert rows["discord_messaging"]["credential_labels"] == ["Bridge Webhook Secret"]
