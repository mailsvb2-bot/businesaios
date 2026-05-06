from __future__ import annotations

from application.decision.action_validator import ActionValidator as _CanonicalActionValidator


class ActionValidator(_CanonicalActionValidator):
    """Compatibility surface for the canonical application action validator."""


CANON_CORE_APPLICATION_ACTION_VALIDATOR_COMPAT = True

__all__ = ["ActionValidator", "CANON_CORE_APPLICATION_ACTION_VALIDATOR_COMPAT"]
