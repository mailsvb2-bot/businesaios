from pathlib import Path
import re

import pytest

from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessGoalEnvelope, IntegrationMode
from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service


TARGETS = (
    Path('application/business_autonomy/operationalization.py'),
    Path('application/business_autonomy/persistence.py'),
)


def test_business_autonomy_tail_contains_no_pass_placeholders() -> None:
    for target in TARGETS:
        text = target.read_text(encoding='utf-8')
        assert re.search(r'^\s*pass\s*$', text, flags=re.M) is None, f'{target} still contains pass placeholder'


@pytest.mark.asyncio
async def test_business_autonomy_execute_persists_audit_evidence_and_planning(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id='site-biz')
    request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id='site-biz',
            goal_id='goal-1',
            goal_type='profile_publish',
            goal_payload={'estimated_cost': 1.0, 'outbound_count': 1},
            metadata={'tenant_id': 'tenant-a', 'planning_horizon': 'week'},
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
        correlation_id='corr-1',
        idempotency_key='idem-1',
    )

    result = await service.execute(request)

    runtime_root = tmp_path / 'business_autonomy'
    assert (runtime_root / 'evidence.jsonl').exists()
    assert (runtime_root / 'planning_memory.jsonl').exists()
    assert (runtime_root / 'idempotency.json').exists()
    assert (runtime_root / 'capabilities.json').exists()
    assert (runtime_root / 'trust.json').exists()
    assert (tmp_path / 'runtime' / 'business_autonomy' / f'{result.execution_id}.json').exists()
    assert (tmp_path / 'runtime' / 'distributed' / 'documents' / 'idempotency_records.json').exists()
