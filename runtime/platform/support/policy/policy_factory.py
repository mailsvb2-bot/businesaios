from __future__ import annotations

CANON_COMPAT_SHIM = True

from core.ai.policy_registry import PolicyRegistry
from runtime.platform.support.policy import PolicyFactory

__all__ = ["PolicyFactory", "PolicyRegistry"]
