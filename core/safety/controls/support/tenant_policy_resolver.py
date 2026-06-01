from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from config.decision_safety_policy import (
    DEFAULT_REWARD_GUARD_POLICY_DEFAULTS,
    DEFAULT_RISK_SCORE_GUARD_POLICY,
    DEFAULT_RISK_SCORER_POLICY,
    DEFAULT_SAFETY_PROFILE_POLICY,
    RewardGuardPolicyDefaults,
    RiskScoreGuardPolicy,
    RiskScorerPolicy,
    SafetyProfilePolicy,
)
from config.tenant_config_store import InMemoryTenantConfigStore, TenantConfigSnapshot
from core.tenancy.normalization import require_tenant_id

from ..policy_manifest import PolicyManifest, PolicyManifestSigner
from ..policy_trust_chain import PolicyTrustChain

CANON_SAFETY_TENANT_POLICY_RESOLVER = True


class TenantSafetyPolicyResolver:
    def __init__(
        self,
        tenant_config_store: InMemoryTenantConfigStore | None = None,
        manifest_signer: PolicyManifestSigner | None = None,
        trust_chain: PolicyTrustChain | None = None,
    ) -> None:
        self._tenant_config_store = tenant_config_store or InMemoryTenantConfigStore()
        self._manifest_signer = manifest_signer or PolicyManifestSigner()
        self._trust_chain = trust_chain or PolicyTrustChain()
        if not self._trust_chain.verify_all():
            raise ValueError('invalid existing safety policy trust chain')

    @property
    def tenant_config_store(self) -> InMemoryTenantConfigStore:
        return self._tenant_config_store

    @property
    def trust_chain(self) -> PolicyTrustChain:
        return self._trust_chain

    def resolve_profile_policy(self, tenant_id: str) -> SafetyProfilePolicy:
        snapshot = self._tenant_snapshot(tenant_id)
        return _merge_dataclass(DEFAULT_SAFETY_PROFILE_POLICY, _policy_overrides(snapshot, 'safety_profile'))

    def resolve_risk_scorer_policy(self, tenant_id: str) -> RiskScorerPolicy:
        snapshot = self._tenant_snapshot(tenant_id)
        return _merge_dataclass(DEFAULT_RISK_SCORER_POLICY, _policy_overrides(snapshot, 'risk_scorer'))

    def resolve_risk_guard_policy(self, tenant_id: str) -> RiskScoreGuardPolicy:
        snapshot = self._tenant_snapshot(tenant_id)
        return _merge_dataclass(DEFAULT_RISK_SCORE_GUARD_POLICY, _policy_overrides(snapshot, 'risk_guard'))

    def resolve_reward_guard_defaults(self, tenant_id: str) -> RewardGuardPolicyDefaults:
        snapshot = self._tenant_snapshot(tenant_id)
        return _merge_dataclass(DEFAULT_REWARD_GUARD_POLICY_DEFAULTS, _policy_overrides(snapshot, 'reward_guard'))

    def manifest_for(self, tenant_id: str, policy_scope: str) -> PolicyManifest:
        snapshot = self._tenant_snapshot(tenant_id)
        overrides = _policy_overrides(snapshot, policy_scope)
        version = None if snapshot is None else snapshot.version
        manifest = self._manifest_signer.build(
            tenant_id=require_tenant_id(tenant_id),
            policy_scope=str(policy_scope),
            policy_payload=overrides,
            version=version,
            source='tenant_config',
        )
        if not self._manifest_signer.verify(manifest):
            raise ValueError('generated safety manifest failed verification')
        self._trust_chain.append(manifest)
        if not self._trust_chain.verify_lineage(
            tenant_id=manifest.tenant_id,
            policy_scope=manifest.policy_scope,
        ):
            raise ValueError('safety trust chain continuity broken')
        return manifest

    def _tenant_snapshot(self, tenant_id: str) -> TenantConfigSnapshot | None:
        try:
            return self._tenant_config_store.get(require_tenant_id(tenant_id))
        except Exception:
            return None


def _policy_overrides(snapshot: TenantConfigSnapshot | None, key: str) -> Mapping[str, Any]:
    if snapshot is None:
        return {}
    raw = dict(snapshot.policy_overrides)
    scoped = raw.get(key)
    return dict(scoped) if isinstance(scoped, Mapping) else {}


def _merge_dataclass(base: Any, overrides: Mapping[str, Any]) -> Any:
    if not overrides:
        return base
    allowed = {field_name: getattr(base, field_name) for field_name in getattr(base, '__dataclass_fields__', {}).keys()}
    merged = dict(allowed)
    for key, value in dict(overrides).items():
        if key in merged:
            merged[key] = value
    return replace(base, **merged)


__all__ = ['CANON_SAFETY_TENANT_POLICY_RESOLVER', 'TenantSafetyPolicyResolver']
