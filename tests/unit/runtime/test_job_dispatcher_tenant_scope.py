from __future__ import annotations

import pytest

from runtime.queue.job_contract import JobDispatchRequest
from runtime.queue.job_dispatcher import JobDispatcher
from runtime.queue.job_store import InMemoryJobStore


def test_job_dispatcher_rejects_cross_tenant_payload() -> None:
    dispatcher = JobDispatcher(store=InMemoryJobStore())
    request = JobDispatchRequest(
        tenant_id='acme',
        job_id='job-1',
        queue_name='campaigns',
        job_type='send_email',
        dedupe_key='d1',
        payload={'tenant_id': 'other', 'queue_name': 'campaigns'},
    )
    with pytest.raises(ValueError):
        dispatcher.dispatch(request)


def test_job_dispatcher_accepts_scoped_payload() -> None:
    dispatcher = JobDispatcher(store=InMemoryJobStore())
    request = JobDispatchRequest(
        tenant_id='acme',
        job_id='job-1',
        queue_name='campaigns',
        job_type='send_email',
        dedupe_key='d1',
        payload={'tenant_id': 'acme', 'queue_name': 'campaigns', 'qualified_job_id': 'tenant/acme/runtime/queue/campaigns/job/job-1'},
    )
    verdict = dispatcher.dispatch(request)
    assert verdict.accepted is True
    assert verdict.job is not None



def test_job_dispatcher_respects_tenant_queue_scope_namespace() -> None:
    dispatcher = JobDispatcher(store=InMemoryJobStore())
    request = JobDispatchRequest(
        tenant_id='acme',
        job_id='job-1',
        queue_name='campaigns',
        job_type='send_email',
        dedupe_key='d1',
        payload={'tenant_queue_scope': {'tenant_id': 'acme', 'queue_name': 'campaigns', 'namespace': 'priority'}},
    )
    verdict = dispatcher.dispatch(request)
    assert verdict.accepted is True
    assert verdict.job is not None
    assert verdict.job.payload['tenant_queue_scope']['namespace'] == 'priority'
    assert verdict.job.payload['qualified_job_id'].startswith('tenant/acme/priority/queue/campaigns/job/')
