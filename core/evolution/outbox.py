"""Evolution outbox (core facade).

Architecture rule: sqlite3 is only allowed inside platform_layer/*.

This module provides:
- a small *runtime* facade (lazy import) used by workers
- stable types for jobs

Core must not import sqlite implementations at module import time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class EvolutionJob:
    job_id: str
    job_kind: str
    payload: dict[str, Any]
    status: str
    created_ms: int
    updated_ms: int
    error: str | None = None


class EvolutionOutbox:
    """Thin delegation wrapper around the concrete outbox implementation."""

    def __init__(self, impl: Any):
        self._impl = impl

    @staticmethod
    def from_env() -> EvolutionOutbox:
        from importlib import import_module

        module = import_module("runtime.platform.outbox.sqlite_evolution_outbox")
        SqliteEvolutionOutbox = getattr(module, "SqliteEvolutionOutbox")
        impl = SqliteEvolutionOutbox(SqliteEvolutionOutbox.default_path_from_env())
        return EvolutionOutbox(impl)

    def enqueue(self, *, job_kind: str, payload: dict[str, Any] | None = None, job_id: str | None = None) -> str:
        return str(self._impl.enqueue(job_kind=str(job_kind), payload=dict(payload or {}), job_id=job_id))

    def list_pending(self, *, limit: int = 10) -> list[EvolutionJob]:
        jobs = self._impl.list_pending(limit=int(limit))
        out: list[EvolutionJob] = []
        for j in jobs:
            out.append(
                EvolutionJob(
                    job_id=str(getattr(j, 'job_id', '')),
                    job_kind=str(getattr(j, 'job_kind', '')),
                    payload=dict(getattr(j, 'payload', {}) or {}),
                    status=str(getattr(j, 'status', '')),
                    created_ms=int(getattr(j, 'created_ms', 0) or 0),
                    updated_ms=int(getattr(j, 'updated_ms', 0) or 0),
                    error=(str(getattr(j, 'error', '')) if getattr(j, 'error', None) is not None else None),
                )
            )
        return out


    def count_pending(self) -> int:
        if hasattr(self._impl, "count_pending"):
            return int(self._impl.count_pending())
        return int(len(self.list_pending(limit=100)))

    def mark_done(self, job_id: str) -> None:
        self._impl.mark_done(str(job_id))

    def mark_failed(self, job_id: str, error: str | None = None) -> None:
        self._impl.mark_failed(str(job_id), error=(str(error) if error else None))

    def get_status(self, job_id: str) -> str | None:
        return self._impl.get_status(str(job_id))
