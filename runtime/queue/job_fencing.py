from __future__ import annotations

"""Process-level fencing helpers for runtime queue workers.

Operational only:
- generate process-scoped worker ownership identifiers
- validate monotonic fencing tokens carried by job leases
- prevent stale workers from committing terminal transitions

This module must never introduce business decisions or a second execution path.
"""

import os
import platform
import threading
import time
from dataclasses import dataclass

CANON_RUNTIME_QUEUE_JOB_FENCING = True

_PROCESS_NONCE = f"{time.time_ns()}-{threading.get_ident()}"


def build_process_scoped_worker_id(*, prefix: str = "runtime-queue-worker") -> str:
    value = str(prefix).strip() or "runtime-queue-worker"
    hostname = platform.node().strip() or "localhost"
    pid = os.getpid()
    return f"{value}@{hostname}:pid={pid}:nonce={_PROCESS_NONCE}"


@dataclass(frozen=True)
class FencingExpectation:
    owner_id: str
    fencing_token: int

    def __post_init__(self) -> None:
        owner = str(self.owner_id).strip()
        if not owner:
            raise ValueError("owner_id is required")
        if int(self.fencing_token) <= 0:
            raise ValueError("fencing_token must be > 0")


def validate_fencing_token(*, fencing_token: int | None, required: bool = False) -> int | None:
    if fencing_token is None:
        if required:
            raise ValueError("fencing_token is required")
        return None
    token = int(fencing_token)
    if token <= 0:
        raise ValueError("fencing_token must be > 0")
    return token


__all__ = [
    "CANON_RUNTIME_QUEUE_JOB_FENCING",
    "FencingExpectation",
    "build_process_scoped_worker_id",
    "validate_fencing_token",
]
