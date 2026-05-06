from runtime.queue import InMemoryJobStore, JobDispatcher

from billing.scheduler.queue_bridge import BillingQueueJobSpec, build_billing_job_request, dispatch_billing_job


def test_build_billing_job_request_stamps_scope_and_lineage() -> None:
    request = build_billing_job_request(
        BillingQueueJobSpec(
            tenant_id='tenant-a',
            job_name='invoice_issue',
            run_key='2026-04-10',
            payload={'invoice_id': 'inv-1'},
            correlation_id='corr-1',
        )
    )

    assert request.job_id == 'billing--invoice_issue--tenant-a--2026-04-10'
    assert request.job_type == 'billing.invoice_issue'
    assert request.dedupe_key == request.job_id
    assert request.payload['tenant_queue_scope']['namespace'] == 'billing'
    assert request.payload['billing_lineage_root'] == 'billing:invoice:inv-1'
    assert 'billing:invoice_issue' in request.tags
    assert 'billing' in request.tags


def test_dispatch_billing_job_is_dedupe_safe_on_replay() -> None:
    dispatcher = JobDispatcher(store=InMemoryJobStore())
    spec = BillingQueueJobSpec(
        tenant_id='tenant-a',
        job_name='renewal',
        run_key='2026-04-10',
        payload={'subscription_ids': ['sub-1']},
    )

    first = dispatch_billing_job(dispatcher=dispatcher, spec=spec)
    second = dispatch_billing_job(dispatcher=dispatcher, spec=spec)

    assert first.accepted is True
    assert second.accepted is True
    assert first.request.job_id == second.request.job_id
    assert second.reason in {'dedupe_existing', 'accepted'}


def test_queue_bridge_rejects_unsupported_job_name() -> None:
    try:
        build_billing_job_request(BillingQueueJobSpec(tenant_id='tenant-a', job_name='dangerous', run_key='rk'))
    except ValueError as exc:
        assert 'unsupported billing job_name' in str(exc)
    else:
        raise AssertionError('expected ValueError for unsupported job_name')
