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


def test_queue_repeated_crash_restart_recovery_soak(tmp_path: Path) -> None:
    db_path = tmp_path / 'queue.sqlite3'
    store = SqliteJobStore(path=db_path)
    now = normalize_now()
    janitor = JobQueueJanitor(store=store)

    for idx in range(3):
        store.put(
            JobDispatchRequest(
                tenant_id='tenant-a',
                job_id=f'job-{idx}',
                queue_name='queue-a',
                job_type='demo',
                payload={'value': idx},
                dedupe_key=f'dedupe-{idx}',
            ).to_record(now=now)
        )

        code = f"""
import sys, time
sys.path.insert(0, {repr(str(Path.cwd()))})
from runtime.queue.job_store_sqlite import SqliteJobStore
from runtime.queue.job_contract import normalize_now
store = SqliteJobStore(path={repr(str(db_path))})
claimed = store.claim(tenant_id='tenant-a', job_id='job-{idx}', owner_id='crash-worker', lease_seconds=1, now=normalize_now())
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
            assert proc.stdout.readline().strip() == 'CLAIMED'
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)

        janitor.tick(tenant_id='tenant-a', queue_name='queue-a', now=now + timedelta(seconds=120 + idx))
        reclaimed = store.claim(
            tenant_id='tenant-a',
            job_id=f'job-{idx}',
            owner_id='recovery-worker',
            lease_seconds=5,
            now=now + timedelta(seconds=121 + idx),
        )
        assert reclaimed is not None
        assert reclaimed.lease is not None
        store.mark_succeeded(
            tenant_id='tenant-a',
            job_id=f'job-{idx}',
            owner_id='recovery-worker',
            fencing_token=reclaimed.lease.fencing_token,
            now=now + timedelta(seconds=122 + idx),
        )

    for idx in range(3):
        final_job = store.get(tenant_id='tenant-a', job_id=f'job-{idx}')
        assert final_job is not None
        assert final_job.state is JobState.SUCCEEDED
