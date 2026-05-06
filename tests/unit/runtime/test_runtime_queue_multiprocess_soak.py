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

    procs = [mp.Process(target=_worker_process, args=(str(db_path), 120)) for _ in range(3)]
    for proc in procs:
        proc.start()
    for _ in range(80):
        janitor.tick(tenant_id='tenant-a', queue_name='ops')
        if store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.SUCCEEDED) == total_jobs:
            break
        time.sleep(0.01)
    for proc in procs:
        proc.join(timeout=10)
        assert proc.exitcode == 0

    assert store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.SUCCEEDED) == total_jobs
    assert store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.PENDING) == 0
    assert store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.CLAIMED) == 0
