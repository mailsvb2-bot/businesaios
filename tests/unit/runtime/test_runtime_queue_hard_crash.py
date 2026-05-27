from __future__ import annotations

import os
import signal
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from runtime.queue.job_contract import JobDispatchRequest, JobState, normalize_now
from runtime.queue.job_janitor import JobQueueJanitor
from runtime.queue.job_store_sqlite import SqliteJobStore


def test_queue_recovers_from_abrupt_process_death(tmp_path: Path) -> None:
    db_path = tmp_path / 'queue.sqlite3'
    store = SqliteJobStore(path=db_path)
    now = normalize_now()
    job = JobDispatchRequest(
        tenant_id='tenant-a',
        job_id='job-a',
        queue_name='queue-a',
        job_type='demo',
        payload={'value': 1},
        dedupe_key='dedupe-a',
    ).to_record(now=now)
    store.put(job)
    code = f"""
import sys, time
sys.path.insert(0, {repr(str(Path.cwd()))})
from runtime.queue.job_store_sqlite import SqliteJobStore
from runtime.queue.job_contract import normalize_now
store = SqliteJobStore(path={repr(str(db_path))})
claimed = store.claim(tenant_id='tenant-a', job_id='job-a', owner_id='crash-worker', lease_seconds=1, now=normalize_now())
assert claimed is not None
print('CLAIMED', flush=True)
time.sleep(60)
"""
    proc = subprocess.Popen(
        [sys.executable, '-c', code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(Path.cwd()),
        env=dict(os.environ),
    )
    try:
        line = proc.stdout.readline().strip()
        assert line == 'CLAIMED'
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)

    janitor = JobQueueJanitor(store=store)
    janitor.tick(tenant_id='tenant-a', queue_name='queue-a', now=now + timedelta(seconds=120))

    claimed_again = store.claim(
        tenant_id='tenant-a',
        job_id='job-a',
        owner_id='recovery-worker',
        lease_seconds=5,
        now=now + timedelta(seconds=121),
    )
    assert claimed_again is not None
    assert claimed_again.lease is not None
    store.mark_succeeded(
        tenant_id='tenant-a',
        job_id='job-a',
        owner_id='recovery-worker',
        fencing_token=claimed_again.lease.fencing_token,
        now=now + timedelta(seconds=122),
    )
    final_job = store.get(tenant_id='tenant-a', job_id='job-a')
    assert final_job is not None
    assert final_job.state is JobState.SUCCEEDED
