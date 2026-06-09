from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from runtime.queue._sqlite_job_store_codec import iso_datetime
from runtime.queue.job_contract import JobState, normalize_now
from runtime.queue.queue_store_policy import DEFAULT_QUEUE_STORE_POLICY


def runtime_queue_sqlite_store_path() -> Path:
    explicit = os.getenv('BUSINESAIOS_JOB_STORE_SQLITE_PATH', '').strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv('DATA_DIR', 'data').strip() or 'data'
    return Path(data_dir) / 'runtime' / 'job_store.sqlite3'


def require_nonempty(value: str, *, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f'{field_name} is required')
    return normalized


def require_job_id(job_id: str) -> str:
    return require_nonempty(job_id, field_name='job_id')


def require_queue_name(queue_name: str) -> str:
    return require_nonempty(queue_name, field_name='queue_name')


def require_owner_id(owner_id: str) -> str:
    return require_nonempty(owner_id, field_name='owner_id')


def require_dedupe_key(dedupe_key: str) -> str:
    return require_nonempty(dedupe_key, field_name='dedupe_key')


def purge_terminal_jobs_sqlite(*, db, tenant_id: str, queue_name: str, states: tuple[JobState, ...], older_than: datetime, limit: int) -> int:
    cutoff = normalize_now(older_than)
    allowed_states = tuple(item.value for item in states if item.is_terminal)
    if not allowed_states:
        return 0
    budget = DEFAULT_QUEUE_STORE_POLICY.normalize_purge_limit(limit)
    if budget == 0:
        return 0
    placeholders = ','.join('?' for _ in allowed_states)
    rows = db.execute(
        f'''
        SELECT job_id
        FROM runtime_queue_jobs
        WHERE tenant_id = ?
          AND queue_name = ?
          AND state IN ({placeholders})
          AND updated_at <= ?
        ORDER BY updated_at ASC, job_id ASC
        LIMIT ?
        ''',
        (tenant_id, queue_name, *allowed_states, iso_datetime(cutoff), budget),
    ).fetchall()
    if not rows:
        return 0
    job_ids = [str(row['job_id']) for row in rows]
    delete_placeholders = ','.join('?' for _ in job_ids)
    db.execute(
        f'DELETE FROM runtime_queue_jobs WHERE tenant_id = ? AND job_id IN ({delete_placeholders})',
        (tenant_id, *job_ids),
    )
    return len(job_ids)
