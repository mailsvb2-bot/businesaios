import sqlite3

import pytest

from application.business_autonomy.contracts import (
    BusinessExecutionRequest,
    BusinessGoalEnvelope,
    IntegrationMode,
    PolicyConstraint,
)
from tests.support.business_autonomy import build_explicitly_onboarded_service


def _simulation_constraints() -> tuple[PolicyConstraint, ...]:
    return (
        PolicyConstraint(name='monthly_budget_limit', value=10.0),
        PolicyConstraint(name='outbound_message_limit', value=10),
    )


@pytest.mark.asyncio
async def test_business_autonomy_bootstrap_uses_durable_distributed_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    service = build_explicitly_onboarded_service(tenant_id='tenant-demo', business_id='site-biz')
    request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id='site-biz',
            goal_id='goal-1',
            goal_type='profile_publish',
            goal_payload={'estimated_cost': 1.0, 'outbound_count': 1},
            simulation=True,
            constraints=_simulation_constraints(),
            metadata={'tenant_id': 'tenant-demo', 'non_ai_mode': 'supervised', 'autonomy_tier': 'supervised'},
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
        correlation_id='corr-1',
        idempotency_key='idem-1',
    )
    result = await service.execute(request)
    assert result.adapter_name == 'website.default'
    assert result.verdict.value == 'simulated'

    state_path = tmp_path / 'runtime' / 'business_autonomy_state.sqlite3'
    assert state_path.is_file()
    connection = sqlite3.connect(state_path)
    try:
        collections = {
            str(row[0])
            for row in connection.execute('SELECT DISTINCT collection FROM distributed_documents')
        }
        cas_scopes = {
            str(row[0])
            for row in connection.execute('SELECT DISTINCT scope FROM distributed_cas')
        }
    finally:
        connection.close()
    assert 'business_registry' in collections
    assert 'idempotency_records' in cas_scopes


@pytest.mark.asyncio
async def test_scoped_idempotency_does_not_cross_business_boundaries(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    site_service = build_explicitly_onboarded_service(tenant_id='tenant-demo', business_id='site-biz')
    bot_service = build_explicitly_onboarded_service(tenant_id='tenant-demo', business_id='bot-biz')

    site_request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id='site-biz',
            goal_id='goal-site',
            goal_type='profile_publish',
            goal_payload={'estimated_cost': 1.0, 'outbound_count': 1},
            simulation=True,
            constraints=_simulation_constraints(),
            metadata={'tenant_id': 'tenant-demo', 'non_ai_mode': 'supervised', 'autonomy_tier': 'supervised'},
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
        correlation_id='corr-site',
        idempotency_key='same-idem',
    )
    bot_request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id='bot-biz',
            goal_id='goal-bot',
            goal_type='communications_write',
            goal_payload={'estimated_cost': 1.0, 'outbound_count': 1},
            simulation=True,
            constraints=_simulation_constraints(),
            metadata={'tenant_id': 'tenant-demo', 'autonomy_tier': 'bounded_autonomy'},
        ),
        integration_mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        correlation_id='corr-bot',
        idempotency_key='same-idem',
    )

    site_result = await site_service.execute(site_request)
    bot_result = await bot_service.execute(bot_request)
    assert site_result.business_id == 'site-biz'
    assert bot_result.business_id == 'bot-biz'
    assert site_result.verdict.value == 'simulated'
    assert bot_result.verdict.value == 'simulated'
    assert site_result.execution_id != bot_result.execution_id
