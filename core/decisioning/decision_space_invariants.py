from __future__ import annotations

from core.decisioning.capability_vocabulary import ALLOWED_ADVISORY_CAPABILITIES

CANON_DECISION_SPACE_INVARIANTS = True

FORBIDDEN_CAPABILITIES_OUTSIDE_CORE: tuple[str, ...] = (
    "choose",
    "finalize",
    "issue_decision",
    "execute",
)

ALLOWED_ADVISORY_CAPABILITY_NAMES: tuple[str, ...] = tuple(capability.name for capability in ALLOWED_ADVISORY_CAPABILITIES)


__all__ = [
    "ALLOWED_ADVISORY_CAPABILITIES",
    "ALLOWED_ADVISORY_CAPABILITY_NAMES",
    "CANON_DECISION_SPACE_INVARIANTS",
    "FORBIDDEN_CAPABILITIES_OUTSIDE_CORE",
]
