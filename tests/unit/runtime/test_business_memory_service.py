from __future__ import annotations

from runtime.platform.business_memory.service import BusinessMemoryService
from runtime.platform.business_memory.store import FileBusinessMemoryStore


def test_business_memory_service_persists_verified_outcomes(tmp_path) -> None:
    service = BusinessMemoryService(store=FileBusinessMemoryStore(root_dir=tmp_path / 'memory'))
    initial = service.get(business_id='biz-1', request_profile={'segment': 'local_services'})
    assert initial['profile']['segment'] == 'local_services'
    updated = service.update_after_step(
        business_id='biz-1',
        action_type='ACTION_CREATE_LISTING',
        feedback={
            'verified': True,
            'verification_status': 'verified',
            'external_refs': ['listing-1'],
            'normalized_outcome': {'lead_count': 2},
            'goal_score': 0.8,
        },
    )
    assert updated['recent_external_refs'] == ['listing-1']
    assert updated['last_verified_outcomes'][0]['action'] == 'ACTION_CREATE_LISTING'
