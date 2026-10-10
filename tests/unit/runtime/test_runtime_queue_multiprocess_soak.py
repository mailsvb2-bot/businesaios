from __future__ import annotations

import multiprocessing as mp
import time

from runtime.queue.job_contract import JobDispatchRequest, JobState
from runtime.queue.job_dispatcher import JobDispatcher
from runtime.queue.job_janitor import JobQueueJanitor
from runtime.queue.job_retry_policy import JobRetryPolicy
from runtime.queue.job_scheduler import JobScheduler
from runtime.queue.job_store import SqlitePersistentJobStore
from runtime.queue.job_worker import JobWorker


def _worker_process(db_path: str, rounds: int) -> None:
    store = SqlitePersistentJobStore(path=db_path)
    scheduler = JobScheduler(store=store)

    def runner(job):
        return {'ok': True, 'status': 'ok'}

    worker = JobWorker(
        worker_id='mp-soak-worker',
        store=store,
        scheduler=scheduler,
        runner=runner,
        retry_policy=JobRetryPolicy(base_delay_seconds=1, max_delay_seconds=1, jitter_seconds=0),
        lease_seconds=5,
    )
    for _ in range(rounds):
        worker.tick(tenant_id='tenant-a', queue_name='ops')
        time.sleep(0.005)


def test_runtime_queue_multiprocess_soak_finishes_all_jobs(tmp_path):
    db_path = tmp_path / 'jobs.sqlite3'
    store = SqlitePersistentJobStore(path=db_path)
    dispatcher = JobDispatcher(store=store)
    janitor = JobQueueJanitor(store=store)
    total_jobs = 64
    for idx in range(total_jobs):
        dispatcher.dispatch(
            JobDispatchRequest(
                tenant_id='tenant-a',
                job_id=f'job-{idx}',
                queue_name='ops',
                job_type='demo',
                payload={'idx': idx},
                dedupe_key=f'd-{idx}',
            )
        )

    ctx = mp.get_context('spawn')
    procs = [ctx.Process(target=_worker_process, args=(str(db_path), 120)) for _ in range(3)]
    for proc in procs:
        proc.start()
    for _ in range(80):
        janitor.tick(tenant_id='tenant-a', queue_name='ops')
        if store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.SUCCEEDED) == total_jobs:
            break
        time.sleep(0.01)
    # A shared deadline accommodates slow process spawn on loaded CI runners
    # while retaining an explicit failure when a worker actually hangs.
    deadline = time.monotonic() + 45
    try:
        for proc in procs:
            proc.join(timeout=max(0, deadline - time.monotonic()))
        unfinished = [proc for proc in procs if proc.is_alive()]
        assert not unfinished, (
            f"queue workers did not exit within 45s: "
            f"{[(proc.pid, proc.exitcode) for proc in unfinished]}"
        )
        assert all(proc.exitcode == 0 for proc in procs), (
            f"queue worker failures: {[(proc.pid, proc.exitcode) for proc in procs]}"
        )
    finally:
        for proc in procs:
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=5)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=5)

    assert store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.SUCCEEDED) == total_jobs
    assert store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.PENDING) == 0
    assert store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.CLAIMED) == 0
