"""Canonical policy rollout resolver.

This is routing-only policy selection logic. It may resolve rollout and canary
state, but must never compute executable actions.
"""

from __future__ import annotations

import hashlib
import hmac

from config.live_canary_policy import (
    DEFAULT_LIVE_CANARY_POLICY,
    LiveCanaryPolicy,
)
from core.policies.domain import PolicyRef, RolloutConfig
from core.policies.registry import PolicyRegistry


class CanaryPolicyResolver:
    def __init__(
        self,
        registry: PolicyRegistry,
        cfg: RolloutConfig,
        live_policy: LiveCanaryPolicy = DEFAULT_LIVE_CANARY_POLICY,
    ):
        self.registry = registry
        self.cfg = cfg
        self.live_policy = live_policy

    @staticmethod
    def _bucket(user_id: str) -> float:
        digest = hashlib.sha256(user_id.encode()).hexdigest()
        return int(digest[:8], 16) / 0xFFFFFFFF

    def _live_bucket(self, *, tenant_id: str, subject_id: str) -> float:
        material = (
            f"live-canary@v1:{self.live_policy.experiment_id}:"
            f"{tenant_id}:{subject_id}"
        ).encode("utf-8")
        digest = hmac.new(
            self.live_policy.assignment_secret.encode("utf-8"),
            material,
            hashlib.sha256,
        ).digest()
        bucket = int.from_bytes(digest[:8], "big") % 10_000
        return bucket / 10_000.0

    def resolve_policy(
        self,
        user_id: str,
        *,
        tenant_id: str = "",
        purpose: str = "",
        eligible: bool = False,
    ) -> PolicyRef:
        active = self.registry.active()
        if not active:
            raise RuntimeError("No active policy")

        canary = self.registry.canary()
        if not canary:
            return active

        subject = str(user_id or "").strip()
        if not subject:
            return active

        if self.live_policy.enabled:
            self.live_policy.assert_valid()
            tenant = str(tenant_id or "").strip()
            purpose_name = str(purpose or "").strip()
            if tenant not in self.live_policy.allowed_tenant_ids:
                return active
            if purpose_name not in self.live_policy.allowed_purposes:
                return active
            if not bool(eligible):
                return active
            bucket = self._live_bucket(tenant_id=tenant, subject_id=subject)
        else:
            bucket = self._bucket(subject)

        return canary if bucket < self.cfg.canary_pct else active

    def select_policy(
        self,
        user_id: str,
        *,
        tenant_id: str = "",
        purpose: str = "",
        eligible: bool = False,
    ) -> PolicyRef:
        return self.resolve_policy(
            user_id,
            tenant_id=tenant_id,
            purpose=purpose,
            eligible=eligible,
        )
