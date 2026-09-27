from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from contracts.task import DurableTask, DurableTaskStatus
from runtime.queue.job_contract import JobClaimExpiryPolicy, JobDispatchRequest, JobPriority

CANON_DURABLE_TASK_QUEUE_ADAPTER = True


def _assert_scope(payload: Mapping[str, Any], *, name: str, expected: str) -> None:
    raw = payload.get(name)
    if raw is not None and str(raw).strip() != expected:
        raise ValueError(f"task queue payload {name} mismatch")


def build_task_job_request(
    *,
    task: DurableTask,
    queue_name: str,
    job_id: str,
    job_type: str,
    dedupe_key: str,
    payload: Mapping[str, Any] | None = None,
    delay_seconds: int = 0,
) -> JobDispatchRequest:
    if task.status is not DurableTaskStatus.READY:
        raise ValueError("only READY durable tasks may be scheduled as new queue jobs")
    body = dict(payload or {})
    _assert_scope(body, name="tenant_id", expected=task.tenant_id)
    _assert_scope(body, name="business_id", expected=task.business_id)
    _assert_scope(body, name="task_id", expected=task.task_id)
    body.update({
        "tenant_id": task.tenant_id,
        "business_id": task.business_id,
        "task_id": task.task_id,
        "task_priority": task.priority,
        "task_conflict_keys": list(task.conflict_keys),
        "durable_task_retry_policy": task.retry_policy.to_dict(),
        "durable_task_timeout_policy": task.timeout_policy.to_dict(),
    })
    suffix = str(dedupe_key or "").strip()
    if not suffix:
        raise ValueError("dedupe_key is required")
    priority = max(int(JobPriority.LOW), min(int(JobPriority.CRITICAL), int(task.priority)))
    expiry_policy = (
        JobClaimExpiryPolicy.RETRY_IF_BUDGET
        if task.retry_policy.retry_ambiguous
        else JobClaimExpiryPolicy.DEAD_LETTER_AMBIGUOUS
    )
    return JobDispatchRequest(
        tenant_id=task.tenant_id,
        job_id=job_id,
        queue_name=queue_name,
        job_type=job_type,
        payload=body,
        dedupe_key=f"durable-task:{task.business_id}:{task.task_id}:{suffix}",
        delay_seconds=delay_seconds,
        priority=priority,
        max_attempts=task.retry_policy.max_attempts,
        claim_expiry_policy=expiry_policy,
        correlation_id=task.task_id,
        tags=("durable_task",),
    )


class TaskQueueAdapter:
    def __init__(self, *, task_registry: Any, dispatcher: Any) -> None:
        if not callable(getattr(task_registry, "get", None)):
            raise ValueError("task_registry must provide get()")
        if not callable(getattr(dispatcher, "dispatch", None)):
            raise ValueError("dispatcher must provide dispatch()")
        self._tasks = task_registry
        self._dispatcher = dispatcher

    def dispatch(self, *, tenant_id: str, business_id: str, task_id: str, queue_name: str, job_id: str, job_type: str, dedupe_key: str, payload: Mapping[str, Any] | None = None, delay_seconds: int = 0) -> Any:
        task = self._tasks.get(tenant_id=tenant_id, business_id=business_id, task_id=task_id)
        request = build_task_job_request(
            task=task,
            queue_name=queue_name,
            job_id=job_id,
            job_type=job_type,
            dedupe_key=dedupe_key,
            payload=payload,
            delay_seconds=delay_seconds,
        )
        return self._dispatcher.dispatch(request)


__all__ = ["CANON_DURABLE_TASK_QUEUE_ADAPTER", "TaskQueueAdapter", "build_task_job_request"]
