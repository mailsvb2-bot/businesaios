from __future__ import annotations

from runtime.queue.job_contract import JobDispatchRequest
from runtime.queue.job_dispatcher import JobDispatcher
from runtime.queue.job_store import InMemoryJobStore


def test_dispatcher_canonicalizes_scope_payload() -> None:
    dispatcher = JobDispatcher(store=InMemoryJobStore())
    verdict = dispatcher.dispatch(JobDispatchRequest(tenant_id='acme', job_id='job-1', queue_name='campaigns', job_type='email', payload={}, dedupe_key='dedupe-1'))
    assert verdict.accepted is True
    payload = dict(verdict.job.payload)
    assert payload['tenant_id'] == 'acme'
    assert payload['queue_name'] == 'campaigns'
    assert payload['qualified_job_id'] == 'tenant/acme/runtime/queue/campaigns/job/job-1'
    assert payload['qualified_dedupe_key'] == 'tenant/acme/runtime/queue/campaigns/dedupe/dedupe-1'
