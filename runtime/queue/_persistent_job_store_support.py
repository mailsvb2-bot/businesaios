from __future__ import annotations

import os
from pathlib import Path

from runtime.queue.job_store_backend import JobStoreBackend


def wrap_flush(store, value):
    store._flush()
    return value


def maybe_flush(store, value):
    if value:
        store._flush()
    return value


def build_default_job_store(*, memory_factory, sqlite_factory, persistent_factory) -> JobStoreBackend:
    mode = os.getenv('BUSINESAIOS_JOB_STORE_BACKEND', 'file').strip().lower()
    if mode == 'memory':
        return memory_factory()
    if mode == 'sqlite':
        return sqlite_factory()
    return persistent_factory()
