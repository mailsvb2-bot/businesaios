from application.public_site.cta_intake import CTALandingIntakeService


def test_cta_persists_user_facing_business_profile(tmp_path) -> None:
    storage = tmp_path / "cta.jsonl"
    service = CTALandingIntakeService(storage_path=str(storage), app_base_url="https://app.example.test")

    created = service.submit(
        payload={
            "business_name": "Северная кофейня",
            "email": "owner@example.test",
            "website": "https://coffee.example.test",
            "industry": "Кофейня",
            "city": "Казань",
            "intent": "connectors",
        }
    )

    assert created.business_profile == {
        "name": "Северная кофейня",
        "website": "https://coffee.example.test",
        "industry": "Кофейня",
        "city": "Казань",
        "goal": "connectors",
        "contact_email": "owner@example.test",
        "profile_complete": True,
    }

    restored = service.get_status(intake_id=created.intake_id)
    assert restored.found is True
    assert restored.business_profile == created.business_profile


def test_cta_restores_profile_for_legacy_rows_without_profile_field(tmp_path) -> None:
    storage = tmp_path / "cta.jsonl"
    service = CTALandingIntakeService(storage_path=str(storage))
    created = service.submit(payload={"business_name": "Legacy", "email": "owner@example.test"})

    status = service.get_status(intake_id=created.intake_id)

    assert status.business_profile["name"] == "Legacy"
    assert status.business_profile["contact_email"] == "owner@example.test"
