"""Canonical policy rollout resolver.

This is routing-only policy selection logic. It may resolve rollout and canary
state, but must never compute executable actions.
"""

from __future__ import annotations

import hashlib
from core.policies.domain import PolicyRef, RolloutConfig
from core.policies.registry import PolicyRegistry

class CanaryPolicyResolver:
    def __init__(self, registry: PolicyRegistry, cfg: RolloutConfig):
        self.registry = registry
        self.cfg = cfg

    @staticmethod
    def _bucket(user_id: str) -> float:
        h = hashlib.sha256(user_id.encode()).hexdigest()
        return int(h[:8], 16) / 0xFFFFFFFF

    def resolve_policy(self, user_id: str) -> PolicyRef:
        active = self.registry.active()
        if not active:
            raise RuntimeError("No active policy")

        canary = self.registry.canary()
        if not canary:
            return active

        return canary if self._bucket(user_id) < self.cfg.canary_pct else active

    def select_policy(self, user_id: str) -> PolicyRef:
        return self.resolve_policy(user_id)
