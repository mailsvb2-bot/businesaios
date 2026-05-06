from __future__ import annotations

from application.decision.action_dispatcher import ActionDispatcher as _CanonicalActionDispatcher


class ActionDispatcher(_CanonicalActionDispatcher):
    """Compatibility surface for the canonical application decision dispatcher."""


CANON_CORE_APPLICATION_ACTION_DISPATCHER_COMPAT = True

__all__ = ["ActionDispatcher", "CANON_CORE_APPLICATION_ACTION_DISPATCHER_COMPAT"]
