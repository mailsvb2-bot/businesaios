from __future__ import annotations

import pytest

from application.public_site.cta_intake import CTALandingIntakeService


def test_business_settings_owner_lifecycle_on_single_canonical_intake_ledger(tmp_path):
    path = tmp_path / "intake.jsonl"
    service = CTALandingIntakeService(storage_path=str(path))
    one = service.submit(
        payload={"business_name": "First", "industry": "services", "selected_providers": ["telegram_bot"]},
        owner_account_id="owner-one",
    )
    two = service.submit(
        payload={"business_name": "Second", "industry": "commerce"},
        owner_account_id="owner-one",
    )
    before = service.read_business_settings(tenant_id=one.tenant_id, business_id=one.business_id)
    assert before["business_name"] == "First"
    assert before["revision"] == 0
    saved = service.update_business_settings(
        tenant_id=one.tenant_id, business_id=one.business_id,
        business_name="First Renamed", activity_description="Consulting",
        timezone_name="Europe/Moscow", expected_revision=0,
        idempotency_key="settings-save-one",
    )
    assert saved["revision"] == 1
    assert saved["business_name"] == "First Renamed"
    assert saved["activity_description"] == "Consulting"
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3
    assert service.update_business_settings(
        tenant_id=one.tenant_id, business_id=one.business_id,
        business_name="First Renamed", activity_description="Consulting",
        timezone_name="Europe/Moscow", expected_revision=0,
        idempotency_key="settings-save-one",
    ) == saved
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3
    with pytest.raises(ValueError, match="idempotency_conflict"):
        service.update_business_settings(
            tenant_id=one.tenant_id, business_id=one.business_id,
            business_name="Tampered", activity_description="Consulting",
            timezone_name="Europe/Moscow", expected_revision=0,
            idempotency_key="settings-save-one",
        )
    with pytest.raises(RuntimeError, match="stale_revision"):
        service.update_business_settings(
            tenant_id=one.tenant_id, business_id=one.business_id,
            business_name="Another", activity_description="Consulting",
            timezone_name="Europe/Moscow", expected_revision=0,
            idempotency_key="settings-save-two",
        )
    with pytest.raises(ValueError, match="timezone_invalid"):
        service.update_business_settings(
            tenant_id=one.tenant_id, business_id=one.business_id,
            business_name="Another", activity_description="Consulting",
            timezone_name="Mars/Olympus", expected_revision=1,
            idempotency_key="settings-save-two",
        )
    reopened = CTALandingIntakeService(storage_path=str(path))
    assert reopened.read_business_settings(tenant_id=one.tenant_id, business_id=one.business_id) == saved
    assert reopened.get_status(intake_id=one.intake_id).business_profile["name"] == "First Renamed"
    assert reopened.get_status(intake_id=two.intake_id).business_profile["name"] == "Second"
    names = {x["business_id"]: x["name"] for x in reopened.list_owner_businesses(owner_account_id="owner-one")}
    assert names == {one.business_id: "First Renamed", two.business_id: "Second"}
    assert len(reopened.list_recent()) == 2
    with pytest.raises(KeyError, match="not_found"):
        reopened.read_business_settings(tenant_id=two.tenant_id, business_id=one.business_id)
