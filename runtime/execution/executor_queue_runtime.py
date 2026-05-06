from __future__ import annotations

from typing import Any


def enqueue_runtime_job(*, executor, request):
    return executor._queue_support.dispatcher.dispatch(request)


def run_queue_tick(*, executor, tenant_id: str, queue_name: str, now=None):
    report = executor._queue_support.worker.tick(tenant_id=tenant_id, queue_name=queue_name, now=now)
    events = getattr(executor, '_events', None)
    if events is not None and hasattr(events, 'emit'):
        try:
            events.emit(
                event_type='runtime_queue_worker_tick',
                source='runtime.executor',
                user_id='system',
                decision_id='queue-worker',
                correlation_id=f'{tenant_id}:{queue_name}',
                payload={
                    'worker_id': report.worker_id,
                    'queue_name': report.queue_name,
                    'claimed': int(report.claimed),
                    'skipped': int(report.skipped),
                    'succeeded': int(report.succeeded),
                    'retried': int(report.retried),
                    'failed': int(report.failed),
                    'dead_lettered': int(report.dead_lettered),
                    'reclaimed_expired_claims': int(report.reclaimed_expired_claims),
                },
            )
        except Exception as emit_exc:
            executor._logger.warning('runtime_queue_worker_tick_emit_failed', exc_info=emit_exc)
    return report


def _campaign_leader(*, executor, method_name: str, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    reliability = getattr(executor, '_reliability', None)
    if reliability is None:
        return None
    method = getattr(reliability, method_name, None)
    if method is None:
        return None
    return method(tenant_id=tenant_id, owner_id=owner_id, ttl_seconds=ttl_seconds, now=now)


def campaign_scheduler_leader(*, executor, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return _campaign_leader(
        executor=executor,
        method_name='campaign_scheduler_leader',
        tenant_id=tenant_id,
        owner_id=owner_id,
        ttl_seconds=ttl_seconds,
        now=now,
    )


def campaign_or_heartbeat_scheduler_leader(*, executor, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return _campaign_leader(
        executor=executor,
        method_name='campaign_or_heartbeat_scheduler_leader',
        tenant_id=tenant_id,
        owner_id=owner_id,
        ttl_seconds=ttl_seconds,
        now=now,
    )


def campaign_recovery_leader(*, executor, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return _campaign_leader(
        executor=executor,
        method_name='campaign_recovery_leader',
        tenant_id=tenant_id,
        owner_id=owner_id,
        ttl_seconds=ttl_seconds,
        now=now,
    )


def campaign_or_heartbeat_recovery_leader(*, executor, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return _campaign_leader(
        executor=executor,
        method_name='campaign_or_heartbeat_recovery_leader',
        tenant_id=tenant_id,
        owner_id=owner_id,
        ttl_seconds=ttl_seconds,
        now=now,
    )


def run_queue_tick_as_leader(*, executor, tenant_id: str, queue_name: str, owner_id: str, ttl_seconds: int | None = None, now=None) -> dict[str, Any] | None:
    leadership = campaign_or_heartbeat_scheduler_leader(
        executor=executor,
        tenant_id=tenant_id,
        owner_id=owner_id,
        ttl_seconds=ttl_seconds,
        now=now,
    )
    if leadership is None:
        return None
    report = run_queue_tick(executor=executor, tenant_id=tenant_id, queue_name=queue_name, now=now)
    return {
        'leadership': {
            'tenant_id': leadership.tenant_id,
            'election_name': leadership.election_name,
            'leader_id': leadership.leader_id,
            'resource': leadership.resource,
            'fencing_token': leadership.fencing_token.as_int(),
            'expires_at': leadership.expires_at.isoformat(),
        },
        'report': report,
    }
