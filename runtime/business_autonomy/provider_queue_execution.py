from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_runtime_contract import ProviderSyncRunResult
from application.business_autonomy.provider_truth_matrix import provider_truth_map
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_media import (
    ProviderMediaPreparationCoordinator,
    provider_media_file_digest,
    public_provider_media_payload,
)
from runtime.business_autonomy.provider_pacing import ProviderPacingCoordinator
from runtime.business_autonomy.provider_runtime_write_guard import ProviderRuntimeWriteGuard
from runtime.queue.job_contract import JobClaimExpiryPolicy, JobDispatchRequest, JobResult
from runtime.queue.job_dispatcher import JobDispatcher
from runtime.queue.job_scheduler import JobScheduler
from runtime.queue.job_store_sqlite import SqliteJobStore
from runtime.queue.job_worker import JobWorker
from security.secret_vault import SecretVault

CANON_PROVIDER_QUEUE_EXECUTION = True
_PROVIDER_QUEUE_NAME = 'provider_sync'


def _native_audio_descriptor(payload: Mapping[str, Any], *, provider_key: str) -> tuple[str, str, str] | None:
    if provider_key not in {'vk_messaging', 'max_messaging'}:
        return None
    raw = payload.get('attachments')
    if not isinstance(raw, list) or not raw:
        return None
    items = [dict(item) for item in raw if isinstance(item, Mapping)]
    if len(items) != 1:
        raise ValueError(f'{provider_key} canonical audio send requires exactly one attachment')
    item = items[0]
    media_type = str(item.get('kind') or item.get('type') or '').strip().casefold()
    if media_type not in {'audio', 'voice'}:
        raise ValueError(f'{provider_key} canonical media attachment type is unsupported')
    source = str(item.get('source') or item.get('path') or '').strip()
    if not source:
        raise ValueError(f'{provider_key} canonical media attachment source is required')
    return source, 'audio', str(item.get('source_digest') or '').strip().lower()


def _bind_native_audio_digest(payload: Mapping[str, Any], *, provider_key: str) -> dict[str, Any]:
    public = dict(payload or {})
    descriptor = _native_audio_descriptor(public, provider_key=provider_key)
    if descriptor is None:
        return public
    source, _media_type, supplied_digest = descriptor
    actual_digest = provider_media_file_digest(source)
    if supplied_digest and supplied_digest != actual_digest:
        raise ValueError('canonical media source digest mismatch')
    attachments = [dict(item) for item in public.get('attachments', ()) if isinstance(item, Mapping)]
    attachments[0]['source_digest'] = actual_digest
    public['attachments'] = attachments
    return public

_PROVIDER_JOB_TYPE = 'provider_sync.dispatch'
def _queue_store_path() -> Path:
    from application.business_autonomy.persistence import business_autonomy_runtime_dir
    return business_autonomy_runtime_dir() / 'queue' / 'provider_sync_jobs.sqlite3'
@dataclass(frozen=True)
class ProviderQueueDispatchResult:
    job_id: str
    queued: bool
    status: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
@dataclass(frozen=True)
class ProviderQueueExecutionRuntime:
    secret_vault: SecretVault
    live_runtime: ProviderLiveSyncRuntime
    store: SqliteJobStore = field(default_factory=lambda: SqliteJobStore(_queue_store_path()))
    write_guard: ProviderRuntimeWriteGuard = field(default_factory=ProviderRuntimeWriteGuard)
    idempotency_store: Any | None = None
    pacing_coordinator: ProviderPacingCoordinator | None = None
    media_preparation: ProviderMediaPreparationCoordinator | None = None
    def enqueue_sync(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, operation: str, mode: str = 'live', payload: Mapping[str, Any] | None = None, queue_name: str = _PROVIDER_QUEUE_NAME, approval_completion_context: Mapping[str, Any] | None = None) -> ProviderQueueDispatchResult:
        normalized_mode = str(mode or 'live').strip().lower() or 'live'
        normalized_operation = str(operation).strip()
        source_payload = dict(payload or {})
        try:
            canonical_payload = _bind_native_audio_digest(source_payload, provider_key=provider.provider_key) if normalized_mode == 'live' and normalized_operation == 'message_send' else source_payload
        except (FileNotFoundError, OSError, ValueError) as exc:
            return ProviderQueueDispatchResult(
                job_id='', queued=False, status='canonical_media_source_invalid',
                metadata={'queue_name': str(queue_name), 'job_type': _PROVIDER_JOB_TYPE, 'provider_key': provider.provider_key, 'fail_closed_before_queue': True, 'reason': exc.__class__.__name__},
            )
        guard_decision = self.write_guard.evaluate(provider=provider, operation=normalized_operation, mode=normalized_mode, tenant_id=str(tenant_id), business_id=str(business_id), payload=canonical_payload, approval_completion_context=approval_completion_context)
        if not guard_decision.allowed:
            return ProviderQueueDispatchResult(
                job_id='', queued=False, status=guard_decision.status,
                metadata={'queue_name': str(queue_name), 'job_type': _PROVIDER_JOB_TYPE, 'provider_key': provider.provider_key, 'provider_write_guard': guard_decision.to_metadata(), 'fail_closed_before_queue': True},
            )
        truth = provider_truth_map().get(provider.provider_key)
        guarded_message_send = normalized_mode == 'live' and normalized_operation == 'message_send' and bool(truth and truth.write_supported and truth.approval_required)
        native_media = _native_audio_descriptor(canonical_payload, provider_key=provider.provider_key) if guarded_message_send else None
        max_media = native_media if provider.provider_key == 'max_messaging' else None
        if native_media is not None and self.media_preparation is None:
            return ProviderQueueDispatchResult(
                job_id='', queued=False, status='canonical_media_preparation_unavailable',
                metadata={'queue_name': str(queue_name), 'job_type': _PROVIDER_JOB_TYPE, 'provider_key': provider.provider_key, 'fail_closed_before_queue': True},
            )
        approval_fingerprint = str(dict(guard_decision.metadata.get('approval') or {}).get('subject_fingerprint') or '').strip()
        execution_identity = approval_fingerprint if guarded_message_send and approval_fingerprint else uuid4().hex
        normalized_payload = {'provider_key': provider.provider_key, 'business_id': str(business_id), 'operation': normalized_operation, 'mode': normalized_mode, 'payload': canonical_payload}
        job_id = f"provider-sync-{provider.provider_key}-{execution_identity[:32]}"
        pacing = None
        if guarded_message_send and provider.provider_key == 'max_messaging' and self.pacing_coordinator is not None:
            recipient_id = str(canonical_payload.get('chat_id') or canonical_payload.get('user_id') or '').strip()
            pacing = self.pacing_coordinator.reserve(
                tenant_id=str(tenant_id),
                business_id=str(business_id),
                provider_key=provider.provider_key,
                recipient_id=recipient_id,
                reservation_id=job_id,
            )
        req = JobDispatchRequest(
            tenant_id=str(tenant_id), job_id=job_id, queue_name=str(queue_name), job_type=_PROVIDER_JOB_TYPE, payload=normalized_payload,
            dedupe_key=f"{provider.provider_key}-{normalized_operation}-{execution_identity}",
            not_before=None if pacing is None else pacing.scheduled_at,
            max_attempts=(6 if provider.provider_key in {'vk_messaging', 'max_messaging', 'email_connector'} else 1) if guarded_message_send else (6 if provider.provider_key in {'vk_messaging', 'max_messaging'} else 8),
            claim_expiry_policy=JobClaimExpiryPolicy.RETRY_IF_BUDGET if (provider.provider_key == 'vk_messaging' or max_media is not None) else (JobClaimExpiryPolicy.DEAD_LETTER_AMBIGUOUS if guarded_message_send else JobClaimExpiryPolicy.RETRY_IF_BUDGET),
            tags=(f"provider:{provider.provider_key}", f"business:{business_id}"),
        )
        dispatch = JobDispatcher(store=self.store, idempotency_store=self.idempotency_store).dispatch(req)
        job = dispatch.job
        job_metadata = {} if job is None else {
            'job_state': job.state.value,
            'job_attempts': int(job.attempts),
            'job_max_attempts': int(job.max_attempts),
            'job_last_error': job.last_error,
        }
        return ProviderQueueDispatchResult(job_id='' if job is None else job.job_id, queued=dispatch.accepted, status='queued' if dispatch.reason == 'accepted' else dispatch.reason, metadata={'queue_name': str(queue_name), 'job_type': _PROVIDER_JOB_TYPE, 'provider_key': provider.provider_key, 'provider_write_guard': guard_decision.to_metadata(), 'idempotency_resolution': dispatch.idempotency_resolution, 'pacing': None if pacing is None else {'scheduled_at': pacing.scheduled_at.isoformat(), 'delay_ms': pacing.delay_ms, 'scope_key': pacing.scope_key}, **job_metadata})
    def tick(self, *, provider_registry: Mapping[str, ProviderDefinition], tenant_id: str, queue_name: str = _PROVIDER_QUEUE_NAME, worker_id: str = 'provider-runtime-worker', job_id: str | None = None) -> Mapping[str, Any]:
        scheduler = JobScheduler(store=self.store)
        worker = JobWorker(worker_id=str(worker_id).strip() or 'provider-runtime-worker', store=self.store, scheduler=scheduler, runner=self._runner(provider_registry))
        report = worker.tick(tenant_id=str(tenant_id), queue_name=str(queue_name), job_id=job_id)
        job = self.store.get(tenant_id=str(tenant_id), job_id=str(job_id)) if job_id else None
        job_metadata = {} if job is None else {
            'job_state': job.state.value,
            'job_attempts': int(job.attempts),
            'job_max_attempts': int(job.max_attempts),
            'job_last_error': job.last_error,
        }
        return {**dict(report.__dict__), 'worker_id': str(worker_id).strip() or 'provider-runtime-worker', **job_metadata}
    def list_jobs(self, *, tenant_id: str, business_id: str | None = None, provider_key: str, queue_name: str = _PROVIDER_QUEUE_NAME, limit: int = 50) -> tuple[dict[str, Any], ...]:
        rows = self.store.list_due(tenant_id=str(tenant_id), queue_name=str(queue_name), limit=int(limit))
        out = []
        for row in rows:
            if str(row.payload.get('provider_key')) != str(provider_key):
                continue
            if business_id is not None and str(row.payload.get('business_id')) != str(business_id):
                continue
            out.append({'job_id': row.job_id, 'job_type': row.job_type, 'queue_name': row.queue_name, 'state': row.state.value, 'attempts': row.attempts, 'run_at': row.run_at.isoformat(), 'payload': {**dict(row.payload), 'payload': public_provider_media_payload(dict(row.payload.get('payload') or {}))}})
        return tuple(out)
    def metrics(self, *, tenant_id: str, queue_name: str = _PROVIDER_QUEUE_NAME) -> Mapping[str, Any]:
        from runtime.queue.job_contract import JobState
        tid = str(tenant_id)
        return {'tenant_id': tid, 'queue_name': str(queue_name), 'pending': self.store.count(tenant_id=tid, queue_name=str(queue_name), state=JobState.PENDING), 'claimed': self.store.count(tenant_id=tid, queue_name=str(queue_name), state=JobState.CLAIMED), 'completed': self.store.count(tenant_id=tid, queue_name=str(queue_name), state=JobState.SUCCEEDED), 'failed': self.store.count(tenant_id=tid, queue_name=str(queue_name), state=JobState.FAILED)}
    def _runner(self, provider_registry: Mapping[str, ProviderDefinition]):
        runtime = self.live_runtime
        def _run(job) -> JobResult:
            payload = dict(job.payload or {})
            provider_key = str(payload.get('provider_key') or '').strip()
            provider = provider_registry[provider_key]
            business_id = str(payload.get('business_id') or '')
            operation = str(payload.get('operation') or '')
            mode = str(payload.get('mode') or 'live')
            source_payload = dict(payload.get('payload') or {})
            media_pre_final = False
            if provider_key == 'max_messaging' and operation == 'message_send' and self.media_preparation is not None:
                descriptor = _native_audio_descriptor(source_payload, provider_key=provider_key)
                if descriptor is not None:
                    source, media_type, source_digest = descriptor
                    source_digest = source_digest or provider_media_file_digest(source)
                    prepared = self.media_preparation.read(tenant_id=job.tenant_id, business_id=business_id, provider_key=provider_key, job_id=job.job_id, media_type=media_type, source_digest=source_digest)
                    media_pre_final = prepared is None
                    desired_policy = JobClaimExpiryPolicy.RETRY_IF_BUDGET if media_pre_final else JobClaimExpiryPolicy.DEAD_LETTER_AMBIGUOUS
                    if job.claim_expiry_policy is not desired_policy and job.lease is not None:
                        job = self.store.set_claim_expiry_policy(tenant_id=job.tenant_id, job_id=job.job_id, policy=desired_policy, owner_id=job.lease.owner_id, fencing_token=job.lease.fencing_token)
            result: ProviderSyncRunResult = runtime.run(provider=provider, tenant_id=job.tenant_id, business_id=business_id, operation=operation, mode=mode, payload=source_payload, attempts=max(1, int(job.attempts)), _queue_job_id=job.job_id)
            ok, retry = bool(result.accepted), dict(result.metadata.get('retry_policy') or {})
            retryable, category = bool(retry.get('retryable')), str(retry.get('category') or 'provider_runtime_error')
            truth = provider_truth_map().get(provider_key)
            guarded_message_send = (
                str(payload.get('mode') or '').strip().lower() == 'live'
                and str(payload.get('operation') or '') == 'message_send'
                and bool(truth and truth.write_supported and truth.approval_required)
            )
            if guarded_message_send:
                retryable = retryable and self._guarded_send_retry_is_safe(provider_key=provider_key, result=result, media_pre_final=media_pre_final)
                if not ok and retryable and provider_key in {'max_messaging', 'email_connector'} and job.lease is not None and job.claim_expiry_policy is not JobClaimExpiryPolicy.RETRY_IF_BUDGET:
                    job = self.store.set_claim_expiry_policy(
                        tenant_id=job.tenant_id,
                        job_id=job.job_id,
                        policy=JobClaimExpiryPolicy.RETRY_IF_BUDGET,
                        owner_id=job.lease.owner_id,
                        fencing_token=job.lease.fencing_token,
                    )
                if not ok and not retryable and self._guarded_send_outcome_is_ambiguous(result=result):
                    category = 'ambiguous_delivery'
            return JobResult(ok=ok, status=result.status, job_id=job.job_id, tenant_id=job.tenant_id, attempts=job.attempts, output={'provider_key': result.provider_key, 'operation': result.operation, 'mode': result.mode, 'metadata': dict(result.metadata or {})}, error=None if ok else (category.upper() if retryable else f'NON_RETRYABLE:{category}'), retry_delay_seconds=int(retry.get('next_delay_seconds') or 0) if retryable else None)
        return _run

    @staticmethod
    def _guarded_send_retry_is_safe(*, provider_key: str, result: ProviderSyncRunResult, media_pre_final: bool = False) -> bool:
        if provider_key == 'vk_messaging':
            # VK messages.send is provider-idempotent when the canonical runtime
            # supplies a stable non-zero random_id for the durable queue job.
            return True
        if provider_key == 'email_connector':
            parsed = dict(result.metadata.get('parsed_response') or {})
            return str(parsed.get('delivery_state') or '') == 'not_attempted' and bool(parsed.get('retryable'))
        if provider_key != 'max_messaging':
            return False
        if media_pre_final:
            return True
        parsed = dict(result.metadata.get('parsed_response') or {})
        category = str(parsed.get('error_category') or '')
        if str(parsed.get('delivery_state') or '') != 'rejected':
            return False
        if category in {'media_preparation', 'media_not_ready', 'media_token_rejected'}:
            return True
        # MAX has no equivalent provider idempotency key. Ordinary message
        # retries are safe only when the provider explicitly rejected the write.
        return category == 'rate_limit' and int(parsed.get('http_status') or 0) == 429

    @staticmethod
    def _guarded_send_outcome_is_ambiguous(*, result: ProviderSyncRunResult) -> bool:
        if bool(result.accepted):
            return False
        parsed = dict(result.metadata.get('parsed_response') or {})
        return not (parsed and str(parsed.get('delivery_state') or '') == 'rejected' and not bool(parsed.get('retryable')))

__all__ = ['CANON_PROVIDER_QUEUE_EXECUTION', 'ProviderQueueDispatchResult', 'ProviderQueueExecutionRuntime']
