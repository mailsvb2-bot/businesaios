from __future__ import annotations

CANON_COMPAT_SHIM = True

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

CANON_STORAGE_COORDINATION = True
logger = logging.getLogger(__name__)


def _best_effort_flock(handle, *, exclusive: bool) -> None:
    try:
        import fcntl  # type: ignore
    except ImportError:
        return
    mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    try:
        fcntl.flock(handle.fileno(), mode)
    except OSError:
        logger.debug('advisory_file_lock: flock acquire failed', exc_info=True)


def _best_effort_unlock(handle) -> None:
    try:
        import fcntl  # type: ignore
    except ImportError:
        return
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        logger.debug('advisory_file_lock: flock release failed', exc_info=True)


@contextmanager
def advisory_file_lock(target_path: str | Path, *, exclusive: bool) -> Iterator[Path]:
    target = Path(target_path)
    lock_path = target.with_suffix(target.suffix + '.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, 'a+b')
    try:
        _best_effort_flock(handle, exclusive=exclusive)
        yield lock_path
    finally:
        try:
            _best_effort_unlock(handle)
            handle.close()
        finally:
            try:
                if lock_path.exists() and lock_path.stat().st_size == 0:
                    lock_path.unlink()
            except OSError:
                logger.debug('advisory_file_lock: cleanup failed for %s', lock_path, exc_info=True)


__all__ = ['CANON_STORAGE_COORDINATION', 'advisory_file_lock']
