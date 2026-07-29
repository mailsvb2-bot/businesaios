"""Compatibility facade for the canonical application evidence owner."""

from __future__ import annotations

from application.evidence.evidence_persistence import (
    CANON_EVIDENCE_PERSISTENCE,
    EvidencePersistenceService,
    PersistenceArtifacts,
    apply_feedback_to_world_state,
)

CANON_MEMORY_EVIDENCE_PERSISTENCE = True
CANON_COMPAT_SHIM = True

__all__ = [
    "CANON_EVIDENCE_PERSISTENCE",
    "CANON_MEMORY_EVIDENCE_PERSISTENCE",
    "EvidencePersistenceService",
    "PersistenceArtifacts",
    "apply_feedback_to_world_state",
]
