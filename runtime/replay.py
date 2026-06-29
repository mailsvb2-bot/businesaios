"""Canonical replay surface.

Replay is intentionally thin: it only loads an already-issued canonical
DecisionEnvelope by decision_id. It must not re-route, re-plan, or mutate
execution state.
"""

from __future__ import annotations

from runtime.decision import DecisionEnvelope

CANON_RUNTIME_REPLAY_THIN_SURFACE = True
CANON_RUNTIME_REPLAY_NO_DECISION_LOGIC = True


class ReplayEngine:
    def __init__(self, decision_archive):
        self._archive = decision_archive

    def replay(self, decision_id: str) -> DecisionEnvelope:
        env = self._archive.get(decision_id)
        if env is None:
            raise KeyError(f"decision_not_found: {decision_id}")
        return env


__all__ = [
    "CANON_RUNTIME_REPLAY_NO_DECISION_LOGIC",
    "CANON_RUNTIME_REPLAY_THIN_SURFACE",
    "ReplayEngine",
]
