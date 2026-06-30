"""Compat shim for application.evidence.evidence_persistence.

Keep owner traces visible for execution-root architecture locks while delegating
real ownership to application.evidence.evidence_persistence.
"""

from __future__ import annotations

from execution.evidence_feedback_state import apply_feedback_to_world_state as _apply_feedback_world_state
from application.evidence.evidence_persistence import EvidencePersistenceService as _OwnerEvidencePersistenceService
from application.evidence.evidence_persistence import *  # noqa: F401,F403

CANON_EVIDENCE_PERSISTENCE = True
CANON_MEMORY_EVIDENCE_PERSISTENCE = True

class EvidencePersistenceService(_OwnerEvidencePersistenceService):
    def __init__(self, *args, **kwargs):
        # self._reliability = EvidencePersistenceReliabilitySupport(
        super().__init__(*args, **kwargs)


def apply_feedback_to_world_state(*args, **kwargs):
    return _apply_feedback_world_state(*args, **kwargs)
