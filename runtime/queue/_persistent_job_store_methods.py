from __future__ import annotations

from pathlib import Path

from runtime.queue._persistent_job_store_support import maybe_flush, wrap_flush
from runtime.queue._json_job_store_persistence import flush_json_job_store_state, load_json_job_store_state, runtime_queue_store_path


def get_path(self) -> Path:
    return self._path


def put(self, job):
    return wrap_flush(self, super(type(self), self).put(job))


def claim(self, **kwargs):
    item = super(type(self), self).claim(**kwargs)
    if item is not None:
        return maybe_flush(self, item)
    return item


def renew_lease(self, **kwargs):
    item = super(type(self), self).renew_lease(**kwargs)
    return maybe_flush(self, item)


def release_claim(self, **kwargs):
    item = super(type(self), self).release_claim(**kwargs)
    return maybe_flush(self, item)


def reap_expired_claims(self, **kwargs):
    changed = super(type(self), self).reap_expired_claims(**kwargs)
    return maybe_flush(self, changed)


def mark_succeeded(self, **kwargs):
    return wrap_flush(self, super(type(self), self).mark_succeeded(**kwargs))


def reschedule(self, **kwargs):
    return wrap_flush(self, super(type(self), self).reschedule(**kwargs))


def mark_failed(self, **kwargs):
    return wrap_flush(self, super(type(self), self).mark_failed(**kwargs))


def mark_dead_letter(self, **kwargs):
    return wrap_flush(self, super(type(self), self).mark_dead_letter(**kwargs))


def purge_terminal_jobs(self, **kwargs):
    changed = super(type(self), self).purge_terminal_jobs(**kwargs)
    return maybe_flush(self, changed)


def _load(self) -> None:
    self._jobs, self._by_dedupe, self._claim_tokens = load_json_job_store_state(self._path)


def _flush(self) -> None:
    flush_json_job_store_state(path=self._path, jobs=self._jobs, claim_tokens=self._claim_tokens)


def init_path(path: str | Path | None) -> Path:
    return Path(path) if path is not None else runtime_queue_store_path()
