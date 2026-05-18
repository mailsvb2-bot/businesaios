from __future__ import annotations

from types import SimpleNamespace

from adapters.api.fastapi.public_routes import _cta_status_response, _cta_submit_response


def test_cta_intake_submit_response_exposes_advisory_contract() -> None:
    result = SimpleNamespace(
        intake_id="intake-123",
        created_at="2026-05-17T00:00:00Z",
        tenant_id="tenant-1",
        business_id="biz-1",
        user_id="user-1",
        onboarding_status="advisory_created",
        app_url="https://app.businessaios.ru/onboarding/intake-123",
        next_actions=["connectors", "autopilot"],
        user_functionality={"workspace_ready": True},
        admin_visibility={"surface": "control-plane"},
        outcome="pending",
    )

    response = _cta_submit_response(result)

    assert response["ok"] is True
    assert response["intake_id"] == "intake-123"
    assert response["created_at"] == "2026-05-17T00:00:00Z"
    assert response["tenant_id"] == "tenant-1"
    assert response["business_id"] == "biz-1"
    assert response["user_id"] == "user-1"
    assert response["onboarding_status"] == "advisory_created"
    assert response["next"]["ui_url"] == "https://app.businessaios.ru/onboarding/intake-123"
    assert response["next_actions"] == ["connectors", "autopilot"]
    assert response["user_functionality"]["workspace_ready"] is True
    assert response["admin_visibility"]["surface"] == "control-plane"
    assert response["measurable_outcome"] == "pending"
    assert response["write_actions_enabled"] is False
    assert response["approval_required_before_execution"] is True


def test_cta_status_response_exposes_found_and_not_found_contracts() -> None:
    status = SimpleNamespace(
        found=True,
        intake_id="intake-123",
        created_at="2026-05-17T00:00:00Z",
        tenant_id="tenant-1",
        business_id="biz-1",
        user_id="user-1",
        onboarding_status="advisory_created",
        next_actions=["connectors"],
        user_functionality={"workspace_ready": True},
        admin_visibility={"surface": "control-plane"},
        outcome="pending",
    )

    response = _cta_status_response(status)

    assert response["ok"] is True
    assert response["found"] is True
    assert response["intake_id"] == "intake-123"
    assert response["created_at"] == "2026-05-17T00:00:00Z"
    assert response["tenant_id"] == "tenant-1"
    assert response["business_id"] == "biz-1"
    assert response["user_functionality"]["workspace_ready"] is True
    assert response["admin_visibility"]["surface"] == "control-plane"

    status.found = False
    response_not_found = _cta_status_response(status)

    assert response_not_found["ok"] is False
    assert response_not_found["error"] == "not_found"
    assert response_not_found["intake_id"] == "intake-123"
