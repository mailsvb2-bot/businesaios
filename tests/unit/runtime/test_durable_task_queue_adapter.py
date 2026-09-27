from __future__ import annotations

import pytest

from contracts.task import DurableTask, DurableTaskStatus, RetryPolicy
from runtime.queue import InMemoryJobStore, JobDispatcher, JobScheduler
from runtime.queue.job_contract import JobClaimExpiryPolicy
from runtime.queue.task_job_adapter import TaskQueueAdapter, build_task_job_request


class _Registry:
    def __init__(self, tasks: dict[str, DurableTask]) -> None:
        self._tasks = tasks

    def get(self, *, tenant_id: str, business_id: str, task_id: str) -> DurableTask:
        task = self._tasks[task_id]
        assert task.tenant_id == tenant_id
        assert task.business_id == business_id
        return task


def _task(
    task_id: str,
    *,
    priority: int = 50,
    retry_ambiguous: bool = False,
    status: DurableTaskStatus = DurableTaskStatus.READY,
) -> DurableTask:
    return DurableTask(
        task_id=task_id,
        tenant_id="tenant-1",
        business_id="business-1",
        status=status,
        priority=priority,
        conflict_keys=("ledger",),
        retry_policy=RetryPolicy(max_attempts=3, retry_ambiguous=retry_ambiguous),
        created_at_ms=1,
        updated_at_ms=1,
    )


def test_task_job_request_preserves_durable_task_execution_contract() -> None:
    request = build_task_job_request(
        task=_task("task-1", priority=90),
        queue_name="email",
        job_id="job-1",
        job_type="send_email",
        dedupe_key="attempt-1",
        payload={"recipient": "a@example.com"},
    )
    assert request.priority == 90
    assert request.max_attempts == 3
    assert request.claim_expiry_policy is JobClaimExpiryPolicy.DEAD_LETTER_AMBIGUOUS
    assert request.dedupe_key.startswith("durable-task-")
    assert len(request.dedupe_key) == len("durable-task-") + 32
    assert all(forbidden not in request.dedupe_key for forbidden in ("/", "\\", ":", "\n", "\r", "\t"))
    assert request.payload["task_id"] == "task-1"
    assert request.payload["task_conflict_keys"] == ["ledger"]
    assert request.payload["durable_task_retry_policy"]["max_attempts"] == 3


def test_task_queue_adapter_rejects_non_ready_and_scope_conflicts() -> None:
    with pytest.raises(ValueError, match="only READY"):
        build_task_job_request(
            task=_task("task-running", status=DurableTaskStatus.RUNNING),
            queue_name="email",
            job_id="job-1",
            job_type="send_email",
            dedupe_key="attempt-1",
        )
    with pytest.raises(ValueError, match="business_id mismatch"):
        build_task_job_request(
            task=_task("task-1"),
            queue_name="email",
            job_id="job-1",
            job_type="send_email",
            dedupe_key="attempt-1",
            payload={"business_id": "other"},
        )


def test_task_queue_uses_existing_scheduler_priority_order() -> None:
    store = InMemoryJobStore()
    dispatcher = JobDispatcher(store=store)
    tasks = {
        "low": _task("low", priority=20),
        "high": _task("high", priority=90),
    }
    adapter = TaskQueueAdapter(
        task_registry=_Registry(tasks),
        dispatcher=dispatcher,
    )
    for task_id in ("low", "high"):
        verdict = adapter.dispatch(
            tenant_id="tenant-1",
            business_id="business-1",
            task_id=task_id,
            queue_name="email",
            job_id=f"job-{task_id}",
            job_type="send_email",
            dedupe_key="initial",
            payload={"recipient": "a@example.com"},
        )
        assert verdict.accepted is True

    batch = JobScheduler(store=store).select_due_jobs(
        tenant_id="tenant-1",
        queue_name="email",
    )
    assert [job.job_id for job in batch.jobs] == ["job-high", "job-low"]


def test_explicit_ambiguous_retry_maps_to_queue_retry_policy() -> None:
    request = build_task_job_request(
        task=_task("task-1", retry_ambiguous=True),
        queue_name="email",
        job_id="job-1",
        job_type="send_email",
        dedupe_key="attempt-1",
    )
    assert request.claim_expiry_policy is JobClaimExpiryPolicy.RETRY_IF_BUDGET
