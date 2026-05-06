from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from core.safety.controls.profile import build_action_controls
from runtime.safety import SafetyControlProfile, SafetyControlService, build_default_profile

CANON_BOOT_WIRING_ONLY = True


def _persistent_enabled() -> bool:
    raw = str(os.getenv('BUSINESAIOS_SAFETY_PERSISTENT', '1')).strip().lower()
    return raw not in {'0', 'false', 'no', 'off'}


@dataclass(frozen=True)
class SafetyControlRuntime:
    profile: SafetyControlProfile
    persistent: bool

    @property
    def action_controls(self) -> SafetyControlService:
        return self.profile.action_controls

    def action_controls_for_tenant(self, tenant_id: str) -> SafetyControlService:
        resolver = self.profile.tenant_policy_resolver
        return build_action_controls(
            profile_policy=resolver.resolve_profile_policy(tenant_id),
            scorer_policy=resolver.resolve_risk_scorer_policy(tenant_id),
            guard_policy=resolver.resolve_risk_guard_policy(tenant_id),
            reward_defaults=resolver.resolve_reward_guard_defaults(tenant_id),
            kill_switch_registry=self.profile.kill_switch_registry,
            circuit_breaker_store=self.profile.circuit_breaker_store,
            action_budget_ledger=self.profile.action_budget_ledger,
            approval_repository=self.profile.approval_repository,
            runaway_loop_store=self.profile.runaway_loop_store,
            action_catalog=self.profile.action_catalog,
            simulation_evidence_verifier=self.profile.simulation_evidence_verifier,
        )


@lru_cache(maxsize=2)
def _build_safety_control_runtime_cached(enabled: bool) -> SafetyControlRuntime:
    return SafetyControlRuntime(profile=build_default_profile(persistent=enabled), persistent=enabled)


def build_safety_control_runtime(*, persistent: bool | None = None) -> SafetyControlRuntime:
    enabled = _persistent_enabled() if persistent is None else bool(persistent)
    return _build_safety_control_runtime_cached(enabled)


def build_runtime_action_controls() -> SafetyControlService:
    return build_safety_control_runtime().action_controls


build_safety_control_runtime.cache_clear = _build_safety_control_runtime_cached.cache_clear  # type: ignore[attr-defined]
