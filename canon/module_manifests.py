from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet

from canon.authority_registry import CanonAuthority


class CanonModuleRole(str, Enum):
    DECISION_ENGINE = "decision_engine"
    APPLICATION_USE_CASE = "application_use_case"
    RUNTIME_EXECUTOR = "runtime_executor"
    STORE = "store"
    GUARD = "guard"
    POLICY = "policy"
    OBSERVABILITY = "observability"


@dataclass(frozen=True)
class CanonModuleManifest:
    module_name: str
    owner: str
    role: CanonModuleRole
    public_exports: tuple[tuple[str, str], ...] = ()
    authorities: FrozenSet[CanonAuthority] = field(default_factory=frozenset)
    allowed_internal_import_prefixes: FrozenSet[str] = field(default_factory=frozenset)
    forbidden_internal_import_prefixes: FrozenSet[str] = field(default_factory=frozenset)
    decision_authority: bool = False
    effect_authority: bool = False
    state_authority: bool = False
    is_compat: bool = False
    canonical_path_member: bool = False


DEFAULT_CANON_MODULE_MANIFESTS: tuple[CanonModuleManifest, ...] = (
    CanonModuleManifest(
        module_name="application.decision",
        owner="application.decision",
        role=CanonModuleRole.DECISION_ENGINE,
        public_exports=(("DecisionCore", "decision.core"), ("DecisionRequest", "decision.request"), ("DecisionResult", "decision.result")),
        authorities=frozenset({CanonAuthority.DECISION}),
        allowed_internal_import_prefixes=frozenset({"application.contracts", "application.policy", "application.world_state", "application.evidence", "application.capability"}),
        forbidden_internal_import_prefixes=frozenset({"runtime", "interfaces", "tools.canon_audit"}),
        decision_authority=True,
        canonical_path_member=True,
    ),
    CanonModuleManifest(
        module_name="application.world_state",
        owner="application.world_state",
        role=CanonModuleRole.APPLICATION_USE_CASE,
        public_exports=(("WorldStateAssembler", "world_state.assembler"), ("WorldStateV1", "world_state.v1")),
        authorities=frozenset({CanonAuthority.WORLD_STATE}),
        allowed_internal_import_prefixes=frozenset({"application.contracts", "application.memory", "application.evidence", "application.policy"}),
        forbidden_internal_import_prefixes=frozenset({"runtime._internal", "tools.canon_audit"}),
        state_authority=True,
        canonical_path_member=True,
    ),
    CanonModuleManifest(
        module_name="application.evidence",
        owner="application.evidence",
        role=CanonModuleRole.STORE,
        public_exports=(("EvidenceService", "evidence.service"), ("EvidenceRecord", "evidence.record")),
        authorities=frozenset({CanonAuthority.EVIDENCE}),
        allowed_internal_import_prefixes=frozenset({"application.contracts", "observability"}),
        canonical_path_member=True,
    ),
    CanonModuleManifest(
        module_name="application.memory",
        owner="application.memory",
        role=CanonModuleRole.STORE,
        public_exports=(("MemoryService", "memory.service"), ("MemorySnapshot", "memory.snapshot")),
        authorities=frozenset({CanonAuthority.MEMORY}),
        allowed_internal_import_prefixes=frozenset({"application.contracts", "application.evidence"}),
        canonical_path_member=True,
    ),
    CanonModuleManifest(
        module_name="application.governance",
        owner="application.governance",
        role=CanonModuleRole.GUARD,
        public_exports=(("ApprovalPolicyEngine", "governance.approval_policy_engine"), ("BudgetGuard", "governance.budget_guard"), ("KillSwitchRegistry", "governance.kill_switch_registry")),
        authorities=frozenset({CanonAuthority.APPROVAL, CanonAuthority.BUDGET, CanonAuthority.KILL_SWITCH}),
        allowed_internal_import_prefixes=frozenset({"application.contracts", "application.policy", "observability"}),
    ),
    CanonModuleManifest(
        module_name="application.capability",
        owner="application.capability",
        role=CanonModuleRole.POLICY,
        public_exports=(("CapabilityVerdictService", "capability.verdict_service"),),
        authorities=frozenset({CanonAuthority.CAPABILITY_VERDICT}),
        allowed_internal_import_prefixes=frozenset({"application.contracts", "application.policy"}),
    ),
    CanonModuleManifest(
        module_name="runtime.execution",
        owner="runtime.execution",
        role=CanonModuleRole.RUNTIME_EXECUTOR,
        public_exports=(("RuntimeExecutor", "runtime.executor"),),
        authorities=frozenset({CanonAuthority.EXECUTION}),
        allowed_internal_import_prefixes=frozenset({"runtime._internal", "application.contracts", "application.evidence", "application.memory", "observability"}),
        forbidden_internal_import_prefixes=frozenset({"application.decision", "tools.canon_audit"}),
        canonical_path_member=True,
    ),
    CanonModuleManifest(
        module_name="runtime._internal",
        owner="runtime._internal",
        role=CanonModuleRole.RUNTIME_EXECUTOR,
        public_exports=(("EffectRouter", "runtime.effect_router"),),
        authorities=frozenset({CanonAuthority.EFFECT}),
        allowed_internal_import_prefixes=frozenset({"runtime._internal", "observability"}),
        forbidden_internal_import_prefixes=frozenset({"application.decision", "application.policy", "tools.canon_audit"}),
        effect_authority=True,
        canonical_path_member=True,
    ),
)

__all__ = ["CanonModuleRole", "CanonModuleManifest", "DEFAULT_CANON_MODULE_MANIFESTS"]
