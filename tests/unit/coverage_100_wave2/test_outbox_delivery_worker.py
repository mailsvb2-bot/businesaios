from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from reliability.outbox_backend import (
    OutboxBackendHealth, OutboxBackendMode, OutboxDeliveryConflict, OutboxDeliveryError,
    OutboxDeliveryReceipt, OutboxDeliveryStatus,
)
from reliability.outbox_delivery_worker import OutboxDeliveryWorker, _transport_name_from_message
from reliability.outbox_store import OutboxMessage, OutboxState

NOW = datetime(2026, 7, 18, tzinfo=UTC)


def _message(**changes):
    values=dict(tenant_id='tenant-a',message_id='message-a',topic='topic-a',dedupe_key='dedupe-a',payload={},
                state=OutboxState.DELIVERING,created_at=NOW,updated_at=NOW,available_at=NOW,
                claim_owner_id='worker',claim_expires_at=NOW+timedelta(minutes=1),delivery_attempts=1,
                delivery_metadata={})
    values.update(changes); return OutboxMessage(**values)


class Metrics:
    def __init__(self): self.calls=[]
    def __getattr__(self,name):
        return lambda **kwargs: self.calls.append((name,kwargs))


class Backend:
    backend_name='backend-a'
    def __init__(self, *, healthy=True, error=None, receipt=None): self.healthy=healthy; self.error=error; self.receipt=receipt; self.delivered=[]
    def healthcheck(self):
        if isinstance(self.healthy, Exception): raise self.healthy
        return OutboxBackendHealth(backend_name=self.backend_name, healthy=self.healthy, mode=OutboxBackendMode.DURABLE, detail='detail')
    def deliver(self,message):
        self.delivered.append(message)
        if self.error: raise self.error
        return self.receipt or OutboxDeliveryReceipt(tenant_id=message.tenant_id,message_id=message.message_id,backend_name=self.backend_name,status=OutboxDeliveryStatus.DELIVERED,delivered_at=NOW,external_id='ext',payload_digest='digest',metadata={'ok':True})


class Store:
    def __init__(self, messages=()): self.messages=list(messages); self.calls=[]; self.claim_none=set()
    def list_claimable(self, **kwargs): self.calls.append(('list',kwargs)); return tuple(self.messages[:kwargs['limit']])
    def claim(self, **kwargs):
        self.calls.append(('claim',kwargs));
        return None if kwargs['message_id'] in self.claim_none else next(m for m in self.messages if m.message_id==kwargs['message_id'])
    def mark_delivered(self, **kwargs):
        self.calls.append(('delivered',kwargs)); m=next(m for m in self.messages if m.message_id==kwargs['message_id']); return SimpleNamespace(state=OutboxState.DELIVERED,delivery_attempts=m.delivery_attempts)
    def move_to_dead_letter(self, **kwargs):
        self.calls.append(('dead',kwargs)); m=next(m for m in self.messages if m.message_id==kwargs['message_id']); return SimpleNamespace(state=OutboxState.DEAD,delivery_attempts=m.delivery_attempts)
    def schedule_retry(self, **kwargs):
        self.calls.append(('retry',kwargs)); m=next(m for m in self.messages if m.message_id==kwargs['message_id']); return SimpleNamespace(state=OutboxState.PENDING,delivery_attempts=m.delivery_attempts)


class Policy:
    def __init__(self, dead=False, delay=0): self.dead=dead; self.delay=delay; self.calls=[]
    def classify(self, **kwargs): self.calls.append(kwargs); return SimpleNamespace(move_to_dead_letter=self.dead,retry_delay_seconds=self.delay)


def test_transport_resolution_metadata_payload_topic_and_fallback() -> None:
    assert _transport_name_from_message(_message(delivery_metadata={'transport':' telegram '}),fallback='x')=='telegram'
    assert _transport_name_from_message(_message(delivery_metadata={'channel':' slack '}),fallback='x')=='slack'
    assert _transport_name_from_message(_message(delivery_metadata={'transport_name':' email '}),fallback='x')=='email'
    assert _transport_name_from_message(_message(payload={'channel':' sms '}),fallback='x')=='sms'
    assert _transport_name_from_message(_message(payload={'transport_name':' push '}),fallback='x')=='push'
    assert _transport_name_from_message(_message(topic=''),fallback=' fallback ')=='fallback'
    assert _transport_name_from_message(_message(topic=''),fallback='')=='outbox'


def test_constructor_descriptor_health_exception_and_unhealthy() -> None:
    metrics=Metrics(); store=Store(); backend=Backend(healthy=RuntimeError('down'))
    worker=OutboxDeliveryWorker(outbox_store=store,backend=backend,worker_id=' ',transport_name=' ',claim_ttl_seconds=0,batch_limit=0,max_consecutive_failures=0,now_factory=lambda:NOW,metrics=metrics)
    desc=worker.descriptor(); assert desc.worker_id=='outbox-delivery-worker' and desc.transport_name=='backend-a'
    report=worker.run_once(tenant_id='tenant-a'); assert report.skipped==1 and 'RuntimeError' in report.reports[0].error
    assert metrics.calls[-1][1]['reason']=='healthcheck_exception'
    backend.healthy=False
    report=worker.run_once(tenant_id='tenant-a'); assert report.skipped==1 and 'unhealthy' in report.reports[0].error
    names=[x[0] for x in metrics.calls]; assert 'record_worker_healthcheck' in names and 'record_skipped' in names


def test_run_once_delivers_skips_and_limit_zero() -> None:
    messages=[_message(message_id='skip'),_message(message_id='ok',delivery_metadata={'channel':'telegram'})]
    store=Store(messages); store.claim_none.add('skip'); metrics=Metrics(); backend=Backend()
    worker=OutboxDeliveryWorker(outbox_store=store,backend=backend,now_factory=lambda:NOW,metrics=metrics)
    zero=worker.run_once(tenant_id='tenant-a',limit=0); assert zero.processed==0 and not any(c[0]=='list' for c in store.calls)
    report=worker.run_once(tenant_id='tenant-a',limit=2)
    assert report.processed==1 and report.delivered==1 and report.skipped==1
    assert report.reports[0].transport_name=='telegram'
    assert {'record_claimed','record_delivered','record_batch'} <= {x[0] for x in metrics.calls}


def test_delivery_errors_retry_dead_letter_and_failure_break() -> None:
    message=_message()
    for error,retryable,dead in [
        (OutboxDeliveryConflict('conflict'),False,True),
        (OutboxDeliveryError('fatal',retryable=True,code='schema_mismatch'),False,True),
        (OutboxDeliveryError('retry',retryable=True,code='temporary'),True,False),
        (RuntimeError('unknown'),True,False),
    ]:
        store=Store([message]); metrics=Metrics(); policy=Policy(dead=dead,delay=0); backend=Backend(error=error)
        worker=OutboxDeliveryWorker(outbox_store=store,backend=backend,dead_letter_policy=policy,now_factory=lambda:NOW,metrics=metrics)
        report=worker.run_once(tenant_id='tenant-a')
        assert report.processed==1 and not report.reports[0].success
        assert policy.calls[0]['retryable'] is retryable
        assert report.dead_lettered==(1 if dead else 0)
        assert report.retried==(0 if dead else 1)
        assert ('record_dead_letter' if dead else 'record_retry') in {x[0] for x in metrics.calls}

    first=_message(message_id='one'); second=_message(message_id='two')
    store=Store([first,second]); worker=OutboxDeliveryWorker(outbox_store=store,backend=Backend(error=RuntimeError('x')),dead_letter_policy=Policy(dead=False),max_consecutive_failures=1,now_factory=lambda:NOW)
    report=worker.run_once(tenant_id='tenant-a',limit=2); assert report.processed==1


def test_success_resets_consecutive_failures_and_unknown_state_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    a=_message(message_id='a'); b=_message(message_id='b'); c=_message(message_id='c')
    store=Store([a,b,c]); worker=OutboxDeliveryWorker(outbox_store=store,backend=Backend(),now_factory=lambda:NOW,max_consecutive_failures=2)
    reports=iter([
        SimpleNamespace(success=False,final_state=OutboxState.PENDING.value),
        SimpleNamespace(success=True,final_state=OutboxState.DELIVERED.value),
        SimpleNamespace(success=False,final_state='unknown'),
    ])
    monkeypatch.setattr(worker,'_deliver_claimed',lambda message: next(reports))
    report=worker.run_once(tenant_id='tenant-a',limit=3)
    assert report.retried==1 and report.delivered==1 and report.skipped==1 and report.processed==3


def test_run_until_drained_zero_and_aggregation(monkeypatch: pytest.MonkeyPatch) -> None:
    worker=OutboxDeliveryWorker(outbox_store=Store(),backend=Backend(),now_factory=lambda:NOW)
    calls=[]
    def run_once(**kwargs):
        calls.append(kwargs)
        if len(calls)==1:
            return SimpleNamespace(processed=2,delivered=1,retried=1,dead_lettered=0,skipped=0,reports=('a','b'))
        return SimpleNamespace(processed=0,delivered=0,retried=0,dead_lettered=0,skipped=0,reports=())
    monkeypatch.setattr(worker,'run_once',run_once)
    zero=worker.run_until_drained(tenant_id='tenant-a',max_batches=0); assert zero.processed==0 and calls==[]
    total=worker.run_until_drained(tenant_id='tenant-a',max_batches=3); assert total.processed==2 and total.delivered==1 and total.retried==1 and len(calls)==2


def test_handle_failure_without_metrics_and_attempts_before_zero() -> None:
    message=_message(delivery_attempts=0)
    store=Store([message]); policy=Policy(dead=True); worker=OutboxDeliveryWorker(outbox_store=store,backend=Backend(),dead_letter_policy=policy,now_factory=lambda:NOW)
    report=worker._handle_failure(message=message,error=ValueError('bad'),retryable=False)
    assert report.attempts_before==0 and report.final_state==OutboxState.DEAD.value
    policy.dead=False; policy.delay=None
    report=worker._handle_failure(message=message,error=ValueError('bad'),retryable=True)
    assert report.final_state==OutboxState.PENDING.value


def test_utc_now_and_success_without_metrics() -> None:
    from reliability.outbox_delivery_worker import utc_now
    assert utc_now().tzinfo is not None
    message=_message(); store=Store([message]); worker=OutboxDeliveryWorker(outbox_store=store,backend=Backend(),now_factory=lambda:NOW)
    report=worker.run_once(tenant_id='tenant-a')
    assert report.delivered==1


def test_health_failures_without_metrics() -> None:
    worker=OutboxDeliveryWorker(outbox_store=Store(),backend=Backend(healthy=RuntimeError('down')),now_factory=lambda:NOW)
    assert worker.run_once(tenant_id='tenant-a').skipped==1
    worker=OutboxDeliveryWorker(outbox_store=Store(),backend=Backend(healthy=False),now_factory=lambda:NOW)
    assert worker.run_once(tenant_id='tenant-a').skipped==1
