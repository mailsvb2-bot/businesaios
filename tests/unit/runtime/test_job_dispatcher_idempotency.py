from __future__ import annotations

from reliability.idempotency_sqlite_backend import SQLiteIdempotencyStore
from runtime.queue.job_contract import JobDispatchRequest
from runtime.queue.job_dispatcher import JobDispatcher
from runtime.queue.job_store import InMemoryJobStore


def _request(*, job_id: str = 'job-1', dedupe_key: str = 'dedupe-1') -> JobDispatchRequest:
    return JobDispatchRequest(
        tenant_id='tenant-1',
        job_id=job_id,
        queue_name='email',
        job_type='send_email',
        payload={'to': 'user@example.com'},
        dedupe_key=dedupe_key,
    )


def test_dispatcher_marks_idempotency_completed_for_accepted_job(tmp_path) -> None:
    dispatcher = JobDispatcher(
        store=InMemoryJobStore(),
        idempotency_store=SQLiteIdempotencyStore(tmp_path / 'queue-idem.sqlite3'),
    )
    verdict = dispatcher.dispatch(_request())
    assert verdict.accepted is True
    assert verdict.idempotency_resolution == 'accepted'


def test_dispatcher_replays_existing_job_when_same_dedupe_key_reused(tmp_path) -> None:
    dispatcher = JobDispatcher(
        store=InMemoryJobStore(),
        idempotency_store=SQLiteIdempotencyStore(tmp_path / 'queue-idem.sqlite3'),
    )
    first = dispatcher.dispatch(_request(job_id='job-1'))
    second = dispatcher.dispatch(_request(job_id='job-2'))
    assert first.accepted is True
    assert second.job is not None and second.job.job_id == 'job-1'
