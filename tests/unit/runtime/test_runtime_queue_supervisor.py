from __future__ import annotations

from time import sleep

from runtime.queue.job_contract import JobDispatchRequest, utc_now
from runtime.queue.job_scheduler import JobScheduler
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.job_worker import JobWorker
from runtime.queue.job_worker_loop import JobWorkerLoop
from runtime.queue.job_worker_supervisor import JobWorkerSupervisor
from runtime.queue.queue_observability import QueueObservabilityRegistry


def _request(job_id: str) -> JobDispatchRequest:
    return JobDispatchRequest(
        tenant_id="tenant-1",
        job_id=job_id,
        queue_name="email",
        job_type="send_email",
        payload={"recipient": f"{job_id}@example.com"},
        dedupe_key=f"dedupe-{job_id}",
    )


def test_worker_loop_stops_gracefully_after_stop_request() -> None:
    store = InMemoryJobStore()
    store.put(_request("job-1").to_record(now=utc_now()))
    processed: list[str] = []

    def runner(job):
        processed.append(job.job_id)
        return {"ok": True}

    worker = JobWorker(
        worker_id="worker-a",
        store=store,
        scheduler=JobScheduler(store=store),
        runner=runner,
    )
    observability = QueueObservabilityRegistry()
    loop = JobWorkerLoop(
        worker=worker,
        tenant_id="tenant-1",
        queue_name="email",
        observability=observability,
        idle_sleep_seconds=0.01,
    )
    loop.stop_token.request_stop(reason="test-stop")
    report = loop.run(max_ticks=10)

    assert report.ticks == 0
    assert processed == []
    snapshot = observability.snapshot()
    assert snapshot.workers[0].heartbeat_state == "stopping"


def test_supervisor_runs_workers_and_emits_observability() -> None:
    store = InMemoryJobStore()
    now = utc_now()
    store.put(_request("job-1").to_record(now=now))
    store.put(_request("job-2").to_record(now=now))

    completed: list[str] = []

    def runner(job):
        completed.append(job.job_id)
        return {"ok": True}

    workers = [
        JobWorker(worker_id="worker-a", store=store, scheduler=JobScheduler(store=store), runner=runner),
        JobWorker(worker_id="worker-b", store=store, scheduler=JobScheduler(store=store), runner=runner),
    ]
    supervisor = JobWorkerSupervisor(
        tenant_id="tenant-1",
        queue_name="email",
        workers=workers,
        idle_sleep_seconds=0.01,
    )

    supervisor.start()
    for _ in range(100):
        saved_1 = store.get(tenant_id="tenant-1", job_id="job-1")
        saved_2 = store.get(tenant_id="tenant-1", job_id="job-2")
        if saved_1 is not None and saved_2 is not None and saved_1.state.value == "succeeded" and saved_2.state.value == "succeeded":
            break
        sleep(0.02)
    supervisor.request_stop(reason="test-drain")
    reports = supervisor.join(timeout_seconds=3.0)

    assert len(reports) == 2
    saved_1 = store.get(tenant_id="tenant-1", job_id="job-1")
    saved_2 = store.get(tenant_id="tenant-1", job_id="job-2")
    assert saved_1 is not None and saved_1.state.value == "succeeded"
    assert saved_2 is not None and saved_2.state.value == "succeeded"
    assert sorted(completed) == ["job-1", "job-2"]

    snapshot = supervisor.observability_snapshot()
    assert len(snapshot.workers) == 2
    assert all(item.heartbeat_state in {"running", "stopping"} for item in snapshot.workers)
