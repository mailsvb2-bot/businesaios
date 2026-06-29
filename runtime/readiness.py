"""Canonical runtime readiness contract.

This root-level module must remain a tiny state validator only. It must not
become a second boot path, registry owner, or decision surface.
"""

from __future__ import annotations

from runtime.runtime_state import RuntimeState

CANON_RUNTIME_READINESS_OWNER = True
CANON_RUNTIME_READINESS_STATE_ONLY = True
CANON_RUNTIME_READINESS_NO_DECISION_LOGIC = True


class Readiness:
    def is_ready(self, state: RuntimeState) -> bool:
        return bool(state.booted and state.ready and not state.shutting_down)


__all__ = [
    "CANON_RUNTIME_READINESS_NO_DECISION_LOGIC",
    "CANON_RUNTIME_READINESS_OWNER",
    "CANON_RUNTIME_READINESS_STATE_ONLY",
    "Readiness",
]
