"""Compatibility facade for the canonical application feedback-state owner."""

from __future__ import annotations

from application.evidence.evidence_feedback_state import apply_feedback_to_world_state

CANON_EVIDENCE_FEEDBACK_STATE = True
CANON_COMPAT_SHIM = True

__all__ = ["CANON_EVIDENCE_FEEDBACK_STATE", "apply_feedback_to_world_state"]
