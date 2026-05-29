from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC

from runtime.queue.job_contract import JobDispatchRequest, JobState
from runtime.queue.job_dispatcher import JobDispatcher
from runtime.queue.job_janitor import JobQueueJanitor
from runtime.queue.job_retry_policy import JobRetryPolicy
from runtime.queue.job_scheduler import JobScheduler
from runtime.queue.job_store import SqlitePersistentJobStore
from runtime.queue.job_worker import JobWorker


def test_runtime_queue_long_run_soak_under_repeated_worker_ticks(tmp_path):
    store = SqlitePersistentJobStore(path=tmp_path / 'jobs.sqlite3')
    dispatcher = JobDispatcher(store=store)
    scheduler = JobScheduler(store=store)
    janitor = JobQueueJanitor(store=store)
    processed: list[str] = []

    def runner(job):
        processed.append(job.job_id)
        return {'ok': True, 'status': 'ok'}

    workers = tuple(
        JobWorker(
            worker_id=f'soak-worker-{idx}',
            store=store,
            scheduler=scheduler,
            runner=runner,
            retry_policy=JobRetryPolicy(base_delay_seconds=1, max_delay_seconds=1, jitter_seconds=0),
            lease_seconds=15,
        )
        for idx in range(4)
    )

    total_jobs = 180
    for idx in range(total_jobs):
        dispatcher.dispatch(
            JobDispatchRequest(
                tenant_id='tenant-a',
                job_id=f'job-{idx}',
                queue_name='ops',
                job_type='demo',
                payload={'idx': idx},
                dedupe_key=f'dedupe-{idx}',
            )
        )

    base_time = datetime.now(UTC) + timedelta(seconds=1)
    idle_rounds = 0
    for tick in range(150):
        now = base_time + timedelta(seconds=tick)
        claimed = 0
        for worker in workers:
            report = worker.tick(tenant_id='tenant-a', queue_name='ops', now=now)
            claimed += int(report.claimed)
        janitor.tick(tenant_id='tenant-a', queue_name='ops', now=now)
        if store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.SUCCEEDED) == total_jobs:
            break
        if claimed == 0:
            idle_rounds += 1
            if idle_rounds > 10:
                break
        else:
            idle_rounds = 0

    assert store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.SUCCEEDED) == total_jobs
    assert store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.PENDING) == 0
    assert store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.CLAIMED) == 0
    assert len(set(processed)) == total_jobs


def test_runtime_queue_stress_mix_with_retries_and_dead_letters(tmp_path):
    store = SqlitePersistentJobStore(path=tmp_path / 'jobs.sqlite3')
    dispatcher = JobDispatcher(store=store)
    scheduler = JobScheduler(store=store)
    janitor = JobQueueJanitor(store=store)
    attempts: dict[int, int] = {}

    def runner(job):
        idx = int(job.payload['idx'])
        attempts[idx] = attempts.get(idx, 0) + 1
        if idx % 13 == 0:
            raise RuntimeError('NON_RETRYABLE terminal-boom')
        if idx % 7 == 0 and attempts[idx] < 2:
            raise TimeoutError('retry-me')
        return {'ok': True, 'status': 'ok'}

    workers = tuple(
        JobWorker(
            worker_id=f'stress-worker-{idx}',
            store=store,
            scheduler=scheduler,
            runner=runner,
            retry_policy=JobRetryPolicy(base_delay_seconds=1, max_delay_seconds=1, jitter_seconds=0),
            lease_seconds=15,
        )
        for idx in range(3)
    )

    total_jobs = 90
    for idx in range(total_jobs):
        dispatcher.dispatch(
            JobDispatchRequest(
                tenant_id='tenant-a',
                job_id=f'job-{idx}',
                queue_name='ops',
                job_type='demo',
                payload={'idx': idx},
                dedupe_key=f'dedupe-{idx}',
            )
        )

    base_time = datetime.now(UTC) + timedelta(seconds=1)
    for tick in range(220):
        now = base_time + timedelta(seconds=tick)
        for worker in workers:
            worker.tick(tenant_id='tenant-a', queue_name='ops', now=now)
        janitor.tick(tenant_id='tenant-a', queue_name='ops', now=now)
        pending = store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.PENDING)
        claimed = store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.CLAIMED)
        if pending == 0 and claimed == 0:
            break

    succeeded = store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.SUCCEEDED)
    dead_letter = store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.DEAD_LETTER)
    failed = store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.FAILED)

    assert succeeded + dead_letter + failed >= int(total_jobs*0.95)
    assert dead_letter >= 1
    assert succeeded >= 1
