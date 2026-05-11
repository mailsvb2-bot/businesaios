import pytest
from unittest.mock import AsyncMock, patch
from frontend.src.App import getJson, postJson

@pytest.mark.asyncio
async def test_cta_intake_submit_and_status():
    mock_result = AsyncMock()
    mock_result.intake_id = "intake-123"
    mock_result.tenant_id = "tenant-1"
    mock_result.business_id = "biz-1"
    mock_result.user_id = "user-1"
    mock_result.onboarding_status = "advisory_created"
    mock_result.next_actions = ["connectors", "autopilot"]
    mock_result.user_functionality = {"workspace_ready": True}
    mock_result.admin_visibility = {"surface": "control-plane"}
    mock_result.outcome = "pending"
    
    with patch('adapters.api.fastapi.public_routes.CTALandingIntakeService.submit', return_value=mock_result):
        response = adapters.api.fastapi.public_routes._cta_submit_response(mock_result)
        assert response['ok'] is True
        assert response['intake_id'] == "intake-123"
        assert response['tenant_id'] == "tenant-1"
        assert response['business_id'] == "biz-1"
        assert response['user_id'] == "user-1"
        assert response['onboarding_status'] == "advisory_created"
        assert response['user_functionality']['workspace_ready'] is True
        assert response['admin_visibility']['surface'] == "control-plane"
        assert response['measurable_outcome'] == "pending"
        assert response['write_actions_enabled'] is False
        assert response['approval_required_before_execution'] is True

    # test _cta_status_response for found=True
    mock_status = AsyncMock()
    mock_status.found = True
    mock_status.intake_id = "intake-123"
    mock_status.tenant_id = "tenant-1"
    mock_status.business_id = "biz-1"
    mock_status.user_id = "user-1"
    mock_status.onboarding_status = "advisory_created"
    mock_status.next_actions = ["connectors"]
    mock_status.user_functionality = {"workspace_ready": True}
    mock_status.admin_visibility = {"surface": "control-plane"}
    mock_status.outcome = "pending"
    response_status = adapters.api.fastapi.public_routes._cta_status_response(mock_status)
    assert response_status['ok'] is True
    assert response_status['found'] is True
    assert response_status['intake_id'] == "intake-123"

    # test _cta_status_response for found=False
    mock_status.found = False
    response_not_found = adapters.api.fastapi.public_routes._cta_status_response(mock_status)
    assert response_not_found['ok'] is False
    assert response_not_found['error'] == 'not_found'
    assert response_not_found['intake_id'] == "intake-123"