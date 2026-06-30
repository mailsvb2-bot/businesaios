"""Recovery execution entrypoint surface.

This module is intentionally a thin delegated entrypoint. Recovery ownership stays in
runtime.executor_recovery_flow; observability is consumed only through the runtime
public surface.
"""

from __future__ import annotations

from runtime.executor_recovery_flow import execute_recovery_flow, has_proof_event
from runtime.observability import bind, clear, snapshot

CANON_RUNTIME_RECOVERY_ENTRYPOINT = True

def execute_recovery_entrypoint(**kwargs):
    bind(runtime_entrypoint="executor_recovery")
    try:
        return execute_recovery_flow(**kwargs)
    finally:
        clear()


__all__ = [
    "CANON_RUNTIME_RECOVERY_ENTRYPOINT",
    "execute_recovery_entrypoint",
    "execute_recovery_flow",
    "has_proof_event",
    "snapshot",
]
