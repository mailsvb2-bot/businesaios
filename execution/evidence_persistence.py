from __future__ import annotations

"""Compat shim for application.evidence.evidence_persistence.

Keep owner traces visible for execution-root architecture locks while delegating
real ownership to application.evidence.evidence_persistence.
"""

from execution.evidence_persistence_feedback import (
    compact_evidence_payload as _compact_evidence_payload,
    compact_verification_payload as _compact_verification_payload,
    persistence_key as _persistence_key,
    refs_from_verification as _refs_from_verification,
)
from execution.evidence_persistence_reliability import EvidencePersistenceReliabilitySupport
from execution.evidence_feedback_state import apply_feedback_to_world_state as _apply_feedback_world_state
from application.evidence.evidence_persistence import EvidencePersistenceService as _OwnerEvidencePersistenceService
from application.evidence.evidence_persistence import apply_feedback_to_world_state as _owner_apply_feedback_to_world_state
from application.evidence.evidence_persistence import *  # noqa: F401,F403

CANON_EVIDENCE_PERSISTENCE = True
CANON_MEMORY_EVIDENCE_PERSISTENCE = True


class EvidencePersistenceService(_OwnerEvidencePersistenceService):
    def __init__(self, *args, **kwargs):
        # self._reliability = EvidencePersistenceReliabilitySupport(
        super().__init__(*args, **kwargs)


def apply_feedback_to_world_state(*args, **kwargs):
    return _apply_feedback_world_state(*args, **kwargs)
