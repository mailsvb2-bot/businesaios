from application.public_site.cta_intake import CTALandingIntakeService


def test_cta_persists_user_facing_business_profile(tmp_path) -> None:
    service = CTALandingIntakeService(storage_path=str(tmp_path / "cta.jsonl"), app_base_url="https://app.example.test")
    created = service.submit(payload={"business_name": "Северная кофейня", "email": "owner@example.test",
                                      "website": "https://coffee.example.test", "industry": "Кофейня", "city": "Казань",
                                      "business_model": "services", "intent": "connectors"})
    assert created.business_profile == {
        "name": "Северная кофейня", "email": "owner@example.test", "contact_email": "owner@example.test",
        "website": "https://coffee.example.test", "industry": "Кофейня", "city": "Казань",
        "business_model": "services", "goal": "connectors", "profile_complete": True,
    }
    restored = service.get_status(intake_id=created.intake_id)
    assert restored.found is True
    assert restored.business_profile == created.business_profile


def test_cta_restores_profile_for_legacy_rows_without_profile_field(tmp_path) -> None:
    service = CTALandingIntakeService(storage_path=str(tmp_path / "cta.jsonl"))
    created = service.submit(payload={"business_name": "Legacy", "email": "owner@example.test"})
    profile = service.get_status(intake_id=created.intake_id).business_profile
    assert (profile["name"], profile["email"], profile["contact_email"], profile["profile_complete"]) == (
        "Legacy", "owner@example.test", "owner@example.test", False,
    )
