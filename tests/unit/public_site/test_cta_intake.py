from __future__ import annotations

import json

from application.public_site.cta_intake import CTALandingIntakeService, public_integration_marketplace


def test_cta_intake_records_row_and_returns_ui_url(tmp_path):
    path = tmp_path / "pilot_applications.jsonl"
    service = CTALandingIntakeService(storage_path=str(path), app_base_url="https://app.businessaios.ru")
    result = service.submit(payload={"email": "test@example.com", "intent": "demo"})
    assert result.intake_id.startswith("cta-")
    assert result.outcome == "intake_recorded"
    assert result.app_url.endswith(result.intake_id)
    rows = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row["intake_id"] == result.intake_id
    assert row["source"] == "public_landing_cta"


def test_cta_intake_status_lookup(tmp_path):
    path = tmp_path / "pilot_applications.jsonl"
    service = CTALandingIntakeService(storage_path=str(path))
    result = service.submit(payload={"email": "a@b.c"})
    found = service.get_status(intake_id=result.intake_id)
    assert found.found is True
    assert found.outcome == "intake_recorded"
    missing = service.get_status(intake_id="cta-missing")
    assert missing.found is False
    assert missing.outcome == "not_found"


def test_self_service_plan_is_truthful_persistent_and_fail_safe(tmp_path):
    market = public_integration_marketplace()
    assert market and all(row["write_supported"] is False for row in market)
    service = CTALandingIntakeService(storage_path=str(tmp_path / "cta.jsonl"))
    result = service.submit(payload={"email": "owner@example.test", "business_name": "North Star", "industry": "services",
                                     "goal": "retention", "selected_providers": ["hubspot", "telegram_bot", "unknown", "hubspot"],
                                     "autonomy_mode": "unlimited"})
    assert result.selected_providers == ("hubspot", "telegram_bot")
    assert result.autonomy_mode == "advisor"
    assert result.user_functionality["autonomy_mode_label"] == "Советник"
    assert result.onboarding_progress["percent"] == 67
    assert result.first_value_preview["requires_real_sync"] is True
    assert result.first_value_preview["contains_estimated_financial_claims"] is False
    assert all(item["write_actions_enabled"] is False for item in result.integration_plan)
    restored = service.get_status(intake_id=result.intake_id)
    assert (restored.business_profile, restored.selected_providers, restored.integration_plan) == (result.business_profile, result.selected_providers, result.integration_plan)
