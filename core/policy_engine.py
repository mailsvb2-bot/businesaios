from __future__ import annotations

"""Compatibility facade for policy registry mutation.

This module is intentionally *not* a second decision engine.

Canonical split:
- ``core.policy`` -> policy lifecycle / rollout / safety / deployment primitives
- ``core.policies`` -> concrete user-facing and product/domain policy handlers
- ``core.policy_engine`` -> historical compatibility facade for registry mutation

Irreversible rollout still must go through the sovereign path:
DecisionCore -> DecisionEnvelope -> RuntimeExecutor.
"""

from typing import Any

from core.ai.policy_registry import PolicyRegistry

CANON_COMPAT_SHIM = True


class PolicyEngine:
    """Minimal policy management facade."""

    def __init__(self, registry: PolicyRegistry) -> None:
        self._registry = registry

    def deploy(self, policy: Any) -> None:
        """Register a policy as available.

        NOTE: This mutates only the registry surface. It does not execute effects,
        switch traffic directly, or bypass DecisionCore.
        """

        self._registry.register(policy)


__all__ = ["CANON_COMPAT_SHIM", "PolicyEngine"]
