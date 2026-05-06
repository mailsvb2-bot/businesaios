import pytest

from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessGoalEnvelope, IntegrationMode
from application.business_autonomy.policy_semantics_guard import PolicySemanticsGuard
from interfaces.api.business_autonomy_route_handlers import build_business_autonomy_route_handlers
from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service


def test_policy_semantics_guard_rejects_conflict() -> None:
    guard = PolicySemanticsGuard()
    with pytest.raises(ValueError):
        guard.normalize(
            {
                'autonomy_tier': 'supervised',
                'autonomy': 'full_autonomy',
            }
        )


@pytest.mark.asyncio
async def test_website_business_uses_supervised_adapter_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id='site-biz')
    request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id='site-biz',
            goal_id='goal-site-1',
            goal_type='profile_publish',
            goal_payload={'estimated_cost': 1.0, 'outbound_count': 1},
            metadata={'tenant_id': 'tenant-demo', 'non_ai_mode': 'supervised', 'autonomy_tier': 'supervised'},
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
        correlation_id='corr-site-1',
        idempotency_key='idem-site-1',
    )
    result = await service.execute(request)
    assert result.adapter_name == 'website.default'
    assert result.metadata['channel_kind'] == 'website'
    assert result.verdict.value in {'accepted', 'completed', 'simulated'}


def test_business_autonomy_fleet_view_surface(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    handlers = build_business_autonomy_route_handlers()
    view = handlers.get_fleet_view()
    assert view['fleet_cards']
    assert any(row['channel_kind'] in {'api_business', 'website', 'chatbot', 'commerce'} for row in view['business_class_rows'])
