from __future__ import annotations

"""Canonical policy selection surface.

Routing-only selection of which policy reference should be used for a given
state. This module must not compute actions or execute effects.
"""

from typing import Optional
import logging

from config.decision_safety_policy import DEFAULT_POLICY_SELECTOR_POLICY, PolicySelectorPolicy

from core.observability.errors import log_exception_throttled
from core.policies.canary import CanaryPolicyResolver
from core.policies.types import RolloutConfig

log = logging.getLogger(__name__)


_V1 = "@" + "v1"
_PURPOSE_POLICY = {
    "ingress_poll": "telegram_ingress" + _V1,
    "payments_reconcile": "payments_reconcile" + _V1,
    "payments_webhook_reconcile": "payments_webhook_reconcile" + _V1,
    "offer_outcome_emit": "offer_outcome_emit" + _V1,
}
_POLICY_DEPLOYMENT_ID = "policy_deployment" + _V1


class PolicySelector:
    def __init__(self, registry, safe_mode_policy_id: Optional[str] = None, rollout_config: Optional[RolloutConfig] = None, policy: PolicySelectorPolicy | None = None):
        self._registry = registry
        self._safe = safe_mode_policy_id
        self._policy = policy or DEFAULT_POLICY_SELECTOR_POLICY
        cfg = rollout_config or RolloutConfig(
            canary_pct=self._policy.default_canary_pct,
            min_decisions=self._policy.default_min_decisions,
            max_error_rate=self._policy.default_max_error_rate,
            auto_promote=self._policy.default_auto_promote,
        )

        class _MetaAdapter:
            def __init__(self, impl):
                self._impl = impl

            def active(self):
                return self._impl.active_ref()

            def canary(self):
                return self._impl.canary_ref()

        self._resolver = CanaryPolicyResolver(_MetaAdapter(registry), cfg)

    def resolve_policy(self, state):
        proposal = getattr(state, "deployment_proposal", None)
        if proposal:
            return self._get_optional(_POLICY_DEPLOYMENT_ID, miss_key="deployment") or self._registry.active()

        meta = getattr(state, "meta", None) or {}
        if isinstance(meta, dict):
            purpose = str(meta.get("purpose") or "").strip()
            policy_id = _PURPOSE_POLICY.get(purpose)
            if policy_id:
                selected = self._get_optional(policy_id, miss_key=purpose)
                if selected is not None:
                    return selected

        if getattr(state, "safe_mode", False) and self._safe:
            return self._registry.get(self._safe)

        cand, pct = self._registry.rollout_config()
        pct_i = self._normalize_rollout_pct(pct)
        self._resolver.cfg = RolloutConfig(
            canary_pct=float(pct_i) / self._policy.rollout_pct_divisor,
            min_decisions=self._policy.default_min_decisions,
            max_error_rate=self._policy.default_max_error_rate,
            auto_promote=self._policy.default_auto_promote,
        )

        if cand and pct_i > self._policy.rollout_pct_floor:
            uid = str(getattr(state, "user_id", ""))
            ref = self._resolver.select_policy(uid)
            return self._registry.get(ref.policy_id)

        return self._registry.active()

    select = resolve_policy

    def _get_optional(self, policy_id: str, *, miss_key: str):
        try:
            return self._registry.get(policy_id)
        except (KeyError, LookupError):
            log_exception_throttled(
                log,
                key=f"policy_selector:missing:{miss_key}",
                msg=f"policy_selector: missing {policy_id}",
            )
            return None

    def _normalize_rollout_pct(self, pct: object) -> int:
        try:
            return max(self._policy.rollout_pct_floor, min(self._policy.rollout_pct_ceiling, int(pct or self._policy.rollout_pct_floor)))
        except (TypeError, ValueError):
            log_exception_throttled(log, key="policy_selector:bad_rollout_pct", msg="policy_selector: bad rollout pct")
            return self._policy.rollout_pct_floor
