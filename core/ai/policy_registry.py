"""Policy registry.

Single source of truth for policy objects selected by DecisionCore.

IMPORTANT:
- Policy activation / rollout changes are SIDE-EFFECTS and must therefore occur
  ONLY via RuntimeExecutor through deploy_policy/rollback_policy decisions.
- Lifecycle state for active/canary references remains owned by ``core.policies``.
- Concrete policy object storage is backed by the shared registry core so that
  generic registry mechanics do not fork into another local engine.
"""

from __future__ import annotations

from core.ai._policy_registry_store import PolicyRegistryStore
from core.policies.registry import PolicyRegistry as _MetaPolicyRegistry
from core.policies.types import PolicyRef
from core.security.call_origin import assert_called_from_bootstrap, assert_called_from_runtime_executor

CANON_CORE_AI_POLICY_REGISTRY_LOCAL_STORE = True

class PolicyRegistry:
    def __init__(self):
        self._policies = PolicyRegistryStore()
        self._meta = _MetaPolicyRegistry()
        self._previous: str | None = None

        # rollout config (candidate + pct) - legacy API preserved
        self._candidate: str | None = None
        self._rollout_pct: int = 0

    def register(self, policy) -> None:
        """Register a policy during system wiring.

        Governance:
          - Runtime/handlers must never register policies.
          - Production deployment/rollback happens via deploy_policy/rollback_policy actions.
        """

        assert_called_from_bootstrap()
        self._policies.replace(policy.id, policy)
        if self._meta.active() is None:
            self._meta.promote(PolicyRef(policy_id=policy.id, version="v1"))

    def activate_bootstrap(self, *, policy_id: str) -> None:
        """Select active policy deterministically during bootstrap wiring."""
        assert_called_from_bootstrap()
        pid = str(policy_id).strip()
        if not pid:
            raise ValueError("EMPTY_POLICY_ID")
        if self._policies.maybe_get(pid) is None:
            raise KeyError(pid)
        self._meta.promote(PolicyRef(policy_id=pid, version="v1"))

    def get(self, pid: str):
        return self._policies.get(pid)

    def maybe_get(self, pid: str):
        key = str(pid).strip()
        if not key:
            return None
        return self._policies.maybe_get(key)

    def registered_policy_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._policies.keys()))

    def active(self):
        ref = self._meta.active()
        if ref is None:
            raise RuntimeError("NO_ACTIVE_POLICY")
        return self._policies.get(ref.policy_id)

    def active_ref(self) -> PolicyRef:
        ref = self._meta.active()
        if ref is None:
            raise RuntimeError("NO_ACTIVE_POLICY")
        return ref

    def rollout_config(self) -> tuple[str | None, int]:
        return self._candidate, int(self._rollout_pct)

    # --- SIDE-EFFECT API (must be called only by runtime/_effects_impl through executor) ---

    def set_rollout(self, *, candidate_policy_id: str, rollout_pct: int) -> None:
        # SIDE-EFFECT: must be executed ONLY through runtime/executor effect window.
        assert_called_from_runtime_executor()
        pid = str(candidate_policy_id)
        pct = int(rollout_pct)
        if self._policies.maybe_get(pid) is None:
            raise KeyError(pid)
        if pct < 0 or pct > 100:
            raise ValueError("BAD_ROLLOUT_PCT")
        if pct >= 100:
            # Full activate, clear rollout
            self._previous = (self._meta.active().policy_id if self._meta.active() else None)
            self._meta.promote(PolicyRef(policy_id=pid, version="v1"))
            self._candidate = None
            self._rollout_pct = 0
            return
        self._meta.register_candidate(PolicyRef(policy_id=pid, version="v1"))
        self._meta.start_canary(PolicyRef(policy_id=pid, version="v1"))
        self._candidate = pid
        self._rollout_pct = pct

    def rollback(self) -> None:
        # SIDE-EFFECT: must be executed ONLY through runtime/executor effect window.
        assert_called_from_runtime_executor()
        # rollback canary + clear rollout
        self._candidate = None
        self._rollout_pct = 0
        self._meta.rollback()
        if self._previous is None:
            return
        self._meta.promote(PolicyRef(policy_id=self._previous, version="v1"))

    def canary_ref(self) -> PolicyRef | None:
        return self._meta.canary()
