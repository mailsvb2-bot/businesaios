"""Compat shim for application.evidence.evidence_feedback_state."""

from __future__ import annotations



from application.evidence.evidence_feedback_state import apply_feedback_to_world_state as _apply_feedback_to_world_state
from application.evidence.evidence_feedback_state import *  # noqa: F401,F403

# project_business_memory_evidence
# project_business_memory_governance_summary
CANON_EVIDENCE_FEEDBACK_STATE = True



def apply_feedback_to_world_state(*args, **kwargs):
    return _apply_feedback_to_world_state(*args, **kwargs)
