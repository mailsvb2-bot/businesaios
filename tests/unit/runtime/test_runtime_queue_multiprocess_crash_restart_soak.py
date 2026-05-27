from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

from runtime.queue.job_contract import JobDispatchRequest, JobState, normalize_now
from runtime.queue.job_dispatcher import JobDispatcher
from runtime.queue.job_janitor import JobQueueJanitor
from runtime.queue.job_store_sqlite import SqliteJobStore


def test_runtime_queue_multiprocess_crash_restart_soak(tmp_path: Path) -> None:
    db_path = tmp_path / 'queue.sqlite3'
    store = SqliteJobStore(path=db_path)
    dispatcher = JobDispatcher(store=store)
    janitor = JobQueueJanitor(store=store)
    for idx in range(6):
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

    code = f"""
import sys, time
sys.path.insert(0, {repr(str(Path.cwd()))})
from runtime.queue.job_store_sqlite import SqliteJobStore
from runtime.queue.job_contract import normalize_now, JobState
store = SqliteJobStore(path={repr(str(db_path))})
claimed = []
for idx in range(3):
    job = store.claim(tenant_id='tenant-a', job_id=f'job-{{idx}}', owner_id='crash-worker', lease_seconds=1, now=normalize_now())
    if job is not None:
        claimed.append(job.job_id)
print(','.join(claimed), flush=True)
time.sleep(60)
"""
    proc = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(Path.cwd()), env=dict(os.environ))
    try:
        claimed_line = proc.stdout.readline().strip()
        assert claimed_line
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)

    now = normalize_now()
    for offset in range(1, 20):
        janitor.tick(tenant_id='tenant-a', queue_name='ops', now=now + timedelta(seconds=offset * 5))
        for idx in range(6):
            current = store.get(tenant_id='tenant-a', job_id=f'job-{idx}')
            if current is None or current.state is JobState.SUCCEEDED:
                continue
            claimed = store.claim(
                tenant_id='tenant-a',
                job_id=current.job_id,
                owner_id='recovery-worker',
                lease_seconds=5,
                now=now + timedelta(seconds=offset * 5 + 1),
            )
            if claimed is None:
                continue
            store.mark_succeeded(
                tenant_id='tenant-a',
                job_id=claimed.job_id,
                owner_id='recovery-worker',
                fencing_token=claimed.lease.fencing_token,
                now=now + timedelta(seconds=offset * 5 + 2),
            )
        if store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.SUCCEEDED) == 6:
            break
        time.sleep(0.01)

    assert store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.SUCCEEDED) == 6
    assert store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.PENDING) == 0
    assert store.count(tenant_id='tenant-a', queue_name='ops', state=JobState.CLAIMED) == 0
