from __future__ import annotations

from application.public_site.cta_intake import CTALandingIntakeService


def test_public_payload_cannot_choose_workspace_identity(tmp_path) -> None:
    service = CTALandingIntakeService(storage_path=str(tmp_path / "intakes.jsonl"))
    payload = {"business_name": "Acme", "email": "owner@example.com", "tenant_id": "tenant-victim", "business_id": "business-victim", "user_id": "user-victim"}
    first = service.submit(payload=payload)
    second = service.submit(payload=payload)

    assert first.tenant_id.startswith("tenant-cta-")
    assert first.business_id.startswith("business-cta-")
    assert first.user_id.startswith("user-cta-")
    assert (first.tenant_id, first.business_id, first.user_id) != ("tenant-victim", "business-victim", "user-victim")
    assert (first.tenant_id, first.business_id, first.user_id) != (second.tenant_id, second.business_id, second.user_id)
    status = service.get_status(intake_id=first.intake_id)
    assert status.found is True
    assert (status.tenant_id, status.business_id, status.user_id) == (first.tenant_id, first.business_id, first.user_id)
