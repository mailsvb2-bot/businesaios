from __future__ import annotations

from runtime.executor_runtime_support import build_executor_queue_support
from runtime.queue.job_dead_letter_store import PersistentJobDeadLetterStore
from runtime.queue.job_store import PersistentJobStore


def test_runtime_queue_support_uses_persistent_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('BUSINESAIOS_JOB_STORE_PATH', str(tmp_path / 'jobs.json'))
    monkeypatch.setenv('BUSINESAIOS_JOB_DEAD_LETTER_STORE_PATH', str(tmp_path / 'dead.json'))
    monkeypatch.delenv('BUSINESAIOS_JOB_STORE_BACKEND', raising=False)
    monkeypatch.delenv('BUSINESAIOS_JOB_DEAD_LETTER_STORE_BACKEND', raising=False)
    support = build_executor_queue_support()
    assert isinstance(support.store, PersistentJobStore)
    assert isinstance(support.dead_letter_store, PersistentJobDeadLetterStore)
