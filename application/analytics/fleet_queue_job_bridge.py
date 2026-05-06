from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.queue.job_contract import JobDispatchRequest
from runtime.queue.job_dispatcher import JobDispatcher


@dataclass(frozen=True)
class AnalyticsFleetQueueJobBridge:
    dispatcher: JobDispatcher
    job_type: str = 'analytics.materialize'

    def enqueue_materialization(
        self,
        *,
        tenant_id: str,
        window_days: int = 30,
        queue_name: str = 'analytics',
        export_path: str | None = None,
        experiment_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_tenant = str(tenant_id)
        normalized_queue = str(queue_name or 'analytics')
        job_id = f'analytics-materialize-{normalized_tenant}-{int(window_days)}'
        export_marker = str(export_path or '').replace('/', '_').replace('\\', '_').replace(':', '_')
        dedupe_key = f'analytics-materialize--{normalized_tenant}--{normalized_queue}--{int(window_days)}--{export_marker}'
        verdict = self.dispatcher.dispatch(
            JobDispatchRequest(
                tenant_id=normalized_tenant,
                job_id=job_id,
                queue_name=normalized_queue,
                job_type=str(self.job_type),
                payload={
                    'tenant_id': normalized_tenant,
                    'window_days': int(window_days),
                    'export_path': export_path,
                    'experiment_id': experiment_id,
                },
                dedupe_key=dedupe_key,
                tags=('analytics', 'materialization', f'tenant-{normalized_tenant}'),
            )
        )
        return {
            'accepted': verdict.accepted,
            'reason': verdict.reason,
            'job_id': None if verdict.job is None else verdict.job.job_id,
            'tenant_id': normalized_tenant,
            'queue_name': normalized_queue,
            'idempotency_resolution': verdict.idempotency_resolution,
        }
