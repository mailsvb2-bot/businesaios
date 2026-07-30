from __future__ import annotations

from core.ai.policy_registry import PolicyRegistry
from runtime.platform.support.policy import PolicyFactory

CANON_COMPAT_SHIM = True

__all__ = ["PolicyFactory", "PolicyRegistry"]
