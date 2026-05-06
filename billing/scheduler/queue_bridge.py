from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from billing.lineage import invoice_lineage_root
from core.tenancy.normalization import require_tenant_id
from runtime.queue import JobDispatchRequest, JobDispatcher, JobPriority


CANON_BILLING_QUEUE_BRIDGE = True
_ALLOWED_BILLING_JOBS = frozenset({'renewal', 'invoice_issue', 'dunning_retry', 'reconciliation'})


class BillingQueueDispatcherContract(Protocol):
    def dispatch(self, request: JobDispatchRequest): ...


@dataclass(frozen=True)
class BillingQueueJobSpec:
    tenant_id: str
    job_name: str
    run_key: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    queue_name: str = 'billing'
    delay_seconds: int = 0
    priority: int = int(JobPriority.NORMAL)
    max_attempts: int = 8
    correlation_id: str | None = None
    causation_id: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        normalized_job = str(self.job_name or '').strip().lower()
        if normalized_job not in _ALLOWED_BILLING_JOBS:
            raise ValueError(f'unsupported billing job_name: {self.job_name}')
        if not str(self.run_key or '').strip():
            raise ValueError('run_key is required')
        if not str(self.queue_name or '').strip():
            raise ValueError('queue_name is required')
        if not isinstance(self.payload, Mapping):
            raise TypeError('payload must be a mapping')
        if int(self.delay_seconds) < 0:
            raise ValueError('delay_seconds must be >= 0')
        if int(self.max_attempts) < 1:
            raise ValueError('max_attempts must be >= 1')

    def normalized_copy(self) -> 'BillingQueueJobSpec':
        self.validate()
        return BillingQueueJobSpec(
            tenant_id=require_tenant_id(self.tenant_id),
            job_name=str(self.job_name).strip().lower(),
            run_key=str(self.run_key).strip(),
            payload=dict(self.payload),
            queue_name=str(self.queue_name).strip(),
            delay_seconds=max(0, int(self.delay_seconds)),
            priority=int(self.priority),
            max_attempts=int(self.max_attempts),
            correlation_id=None if self.correlation_id is None else str(self.correlation_id).strip(),
            causation_id=None if self.causation_id is None else str(self.causation_id).strip(),
            tags=tuple(str(tag).strip() for tag in self.tags if str(tag).strip()),
        )

    @property
    def job_id(self) -> str:
        normalized = self.normalized_copy()
        return f'billing--{normalized.job_name}--{normalized.tenant_id}--{normalized.run_key}'

    @property
    def dedupe_key(self) -> str:
        normalized = self.normalized_copy()
        return f'billing--{normalized.job_name}--{normalized.tenant_id}--{normalized.run_key}'

    @property
    def job_type(self) -> str:
        normalized = self.normalized_copy()
        return f'billing.{normalized.job_name}'


@dataclass(frozen=True)
class BillingQueueDispatchResult:
    accepted: bool
    reason: str
    request: JobDispatchRequest
    job_id: str | None = None
    dedupe_resolution: str | None = None


def build_billing_job_request(spec: BillingQueueJobSpec) -> JobDispatchRequest:
    normalized = spec.normalized_copy()
    payload = dict(normalized.payload)
    payload.setdefault('tenant_id', normalized.tenant_id)
    payload.setdefault('billing_job_name', normalized.job_name)
    payload.setdefault('billing_run_key', normalized.run_key)
    payload.setdefault('billing_job_id', normalized.job_id)
    payload.setdefault('billing_dedupe_key', normalized.dedupe_key)
    payload.setdefault('owner', 'billing.scheduler.queue_bridge')
    payload.setdefault('tenant_queue_scope', {
        'tenant_id': normalized.tenant_id,
        'queue_name': normalized.queue_name,
        'namespace': 'billing',
        'scope_key': f'tenant/{normalized.tenant_id}/billing/queue/{normalized.queue_name}',
    })
    invoice_id = str(payload.get('invoice_id') or '').strip()
    if invoice_id:
        payload.setdefault('billing_lineage_root', invoice_lineage_root(invoice_id))
    tags = tuple(dict.fromkeys((*(normalized.tags or ()), f'billing:{normalized.job_name}', 'billing')))
    return JobDispatchRequest(
        tenant_id=normalized.tenant_id,
        job_id=normalized.job_id,
        queue_name=normalized.queue_name,
        job_type=normalized.job_type,
        payload=payload,
        dedupe_key=normalized.dedupe_key,
        delay_seconds=normalized.delay_seconds,
        priority=normalized.priority,
        max_attempts=normalized.max_attempts,
        correlation_id=normalized.correlation_id,
        causation_id=normalized.causation_id,
        tags=tags,
    )


def dispatch_billing_job(*, dispatcher: BillingQueueDispatcherContract, spec: BillingQueueJobSpec) -> BillingQueueDispatchResult:
    request = build_billing_job_request(spec)
    verdict = dispatcher.dispatch(request)
    accepted = bool(getattr(verdict, 'accepted', False))
    reason = str(getattr(verdict, 'reason', 'unknown')).strip() or 'unknown'
    job = getattr(verdict, 'job', None)
    job_id = None if job is None else str(getattr(job, 'job_id', '') or '').strip() or None
    dedupe_resolution = getattr(verdict, 'idempotency_resolution', None)
    return BillingQueueDispatchResult(
        accepted=accepted,
        reason=reason,
        request=request,
        job_id=job_id,
        dedupe_resolution=None if dedupe_resolution is None else str(dedupe_resolution),
    )


__all__ = [
    'BillingQueueDispatchResult',
    'BillingQueueDispatcherContract',
    'BillingQueueJobSpec',
    'CANON_BILLING_QUEUE_BRIDGE',
    'build_billing_job_request',
    'dispatch_billing_job',
]
