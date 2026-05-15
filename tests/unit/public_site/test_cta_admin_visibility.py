from __future__ import annotations

from application.public_site.cta_intake import CTALandingIntakeService
from adapters.api.fastapi.public_routes import _cta_status_response, _cta_submit_response


def test_cta_submit_records_read_only_admin_visibility(tmp_path):
    service = CTALandingIntakeService(
        storage_path=str(tmp_path / "pilot_applications.jsonl"),
        app_base_url="https://app.example.test",
    )

    result = service.submit(
        payload={
            "business_name": "Acme Clinic",
            "email": "owner@example.test",
        }
    )

    assert result.tenant_id.startswith("tenant-")
    assert result.business_id.startswith("business-")
    assert result.user_id.startswith("user-")
    assert result.onboarding_status == "advisory_intake_created"
    assert result.admin_visibility is not None
    assert result.admin_visibility["surface"] == "control_plane.public_site_cta_intakes"
    assert result.admin_visibility["write_actions_enabled"] is False
    assert result.user_functionality is not None
    assert "provider_write_actions" in result.user_functionality["blocked_until_approval"]

    response = _cta_submit_response(result)
    assert response["ok"] is True
    assert response["tenant_id"] == result.tenant_id
    assert response["business_id"] == result.business_id
    assert response["user_id"] == result.user_id
    assert response["write_actions_enabled"] is False
    assert response["approval_required_before_execution"] is True
    assert response["admin_visibility"]["surface"] == "control_plane.public_site_cta_intakes"


def test_cta_status_preserves_admin_visibility(tmp_path):
    service = CTALandingIntakeService(
        storage_path=str(tmp_path / "pilot_applications.jsonl"),
        app_base_url="https://app.example.test",
    )
    submitted = service.submit(payload={"company": "Demo Business", "telegram": "@demo_owner"})

    status = service.get_status(intake_id=submitted.intake_id)
    response = _cta_status_response(status)

    assert response["ok"] is True
    assert response["found"] is True
    assert response["intake_id"] == submitted.intake_id
    assert response["tenant_id"] == submitted.tenant_id
    assert response["business_id"] == submitted.business_id
    assert response["user_id"] == submitted.user_id
    assert response["write_actions_enabled"] is False
    assert response["approval_required_before_execution"] is True
    assert response["admin_visibility"]["write_actions_enabled"] is False


def test_cta_status_not_found_response_is_safe():
    response = _cta_status_response(
        type(
            "MissingStatus",
            (),
            {
                "found": False,
                "intake_id": "cta-missing",
            },
        )()
    )

    assert response == {
        "ok": False,
        "error": "not_found",
        "intake_id": "cta-missing",
    }
