from __future__ import annotations

from dataclasses import dataclass

from config.decision_safety_policy import (
    DEFAULT_RISK_SCORE_GUARD_POLICY,
    DEFAULT_RISK_SCORER_POLICY,
    DEFAULT_REWARD_GUARD_POLICY_DEFAULTS,
    DEFAULT_SAFETY_PROFILE_POLICY,
    RewardGuardPolicyDefaults,
    RiskScoreGuardPolicy,
    RiskScorerPolicy,
    SafetyProfilePolicy,
)
from config.tenant_config_store import InMemoryTenantConfigStore, PersistentTenantConfigStore

from .action_budget.guard import ActionBudgetGuard
from .action_budget.ledger import InMemoryActionBudgetLedger, SqliteActionBudgetLedger
from .action_budget.models import ActionBudget
from .action_catalog import ActionSafetyCatalog, build_default_action_catalog
from .blast_radius.analyzer import StaticBlastRadiusAnalyzer
from .blast_radius.guard import BlastRadiusGuard
from .blast_radius.models import BlastRadiusBudget
from .blast_radius.policy import BlastRadiusPolicy
from .circuit_breaker.feedback import CircuitBreakerFeedback
from .circuit_breaker.guard import CircuitBreakerGuard
from .circuit_breaker.policy import CircuitBreakerPolicy
from .circuit_breaker.store import InMemoryCircuitBreakerStore, SqliteCircuitBreakerStore
from .decision_sandbox.executor import PredicateSandboxExecutor
from .decision_sandbox.guard import DecisionSandboxGuard
from .kill_switch.guard import KillSwitchGuard
from .kill_switch.registry import InMemoryKillSwitchRegistry
from .multi_step_approval.guard import MultiStepApprovalGuard
from .multi_step_approval.models import ApprovalPolicy
from .multi_step_approval.repository import InMemoryApprovalRepository, SqliteApprovalRepository
from .observability.event_store import JsonlSafetyEventStore
from observability.tenant_metrics_registry import TenantMetricsRegistry
from .reward_guard.guard import RewardGuard
from .reward_guard.models import RewardGuardPolicy
from .risk_scoring.guard import RiskScoreGuard
from .risk_scoring.scorer import RiskScorer
from .rollback_engine.registry import InMemoryRollbackRegistry
from .boot_integrity import SafetyBootIntegrityChecker
from .key_registry import SafetyKeyRegistry
from .policy_manifest import PolicyManifestSigner
from .policy_trust_chain import PolicyTrustChain
from .rollback_engine.service import RollbackPlanner
from .rollback_verifier import RollbackVerifier
from .rollback_engine.store import InMemoryRollbackPlanStore, SqliteRollbackPlanStore
from .runaway_loop_guard.guard import RunawayLoopGuard
from .runaway_loop_guard.store import InMemoryRunawayLoopStore, SqliteRunawayLoopStore
from .service import SafetyControlService
from .simulation_gate.evidence import SimulationEvidenceVerifier
from .simulation_gate.models import SimulationGatePolicy
from .simulation_gate.service import SimulationGate
from .support.runtime_paths import safety_jsonl_path, safety_sqlite_path
from .safety_supervisor import SafetySupervisor
from .support.tenant_policy_resolver import TenantSafetyPolicyResolver


@dataclass(frozen=True)
class SafetyControlProfile:
    action_controls: SafetyControlService
    kill_switch_registry: object
    circuit_breaker_store: object
    circuit_breaker_feedback: CircuitBreakerFeedback
    action_budget_ledger: object
    approval_repository: object
    runaway_loop_store: object
    rollback_planner: RollbackPlanner
    action_catalog: ActionSafetyCatalog
    tenant_policy_resolver: TenantSafetyPolicyResolver
    event_store: JsonlSafetyEventStore
    simulation_evidence_verifier: SimulationEvidenceVerifier
    tenant_metrics_registry: TenantMetricsRegistry
    policy_manifest_signer: PolicyManifestSigner
    policy_trust_chain: PolicyTrustChain
    rollback_verifier: RollbackVerifier
    safety_supervisor: SafetySupervisor


def _reject_negative_amount(ctx, *, policy: SafetyProfilePolicy = DEFAULT_SAFETY_PROFILE_POLICY):
    raw = dict(ctx.payload)
    amount = float(raw.get("amount", policy.negative_amount_floor) or policy.negative_amount_floor)
    if amount < policy.negative_amount_floor:
        return "negative_amount_not_allowed"
    return None


def _default_blast_radius_policy(policy: SafetyProfilePolicy) -> BlastRadiusPolicy:
    return BlastRadiusPolicy(
        default_budget=BlastRadiusBudget(
            financial_amount=policy.default_blast_radius_financial_amount,
            users_affected=policy.default_blast_radius_users_affected,
            records_affected=policy.default_blast_radius_records_affected,
            services_touched=policy.default_blast_radius_services_touched,
        ),
        per_prefix_budget={
            policy.capture_payment_prefix: BlastRadiusBudget(
                financial_amount=policy.capture_payment_financial_amount,
                users_affected=policy.capture_payment_users_affected,
                records_affected=policy.capture_payment_records_affected,
                services_touched=policy.capture_payment_services_touched,
            ),
            policy.marketing_offer_prefix: BlastRadiusBudget(
                financial_amount=policy.marketing_offer_financial_amount,
                users_affected=policy.marketing_offer_users_affected,
                records_affected=policy.marketing_offer_records_affected,
                services_touched=policy.marketing_offer_services_touched,
            ),
        },
    )


def build_action_controls(
    *,
    profile_policy: SafetyProfilePolicy,
    scorer_policy: RiskScorerPolicy,
    guard_policy: RiskScoreGuardPolicy,
    reward_defaults: RewardGuardPolicyDefaults,
    kill_switch_registry: object,
    circuit_breaker_store: object,
    action_budget_ledger: object,
    approval_repository: object,
    runaway_loop_store: object,
    action_catalog: ActionSafetyCatalog,
    simulation_evidence_verifier: SimulationEvidenceVerifier,
) -> SafetyControlService:
    return SafetyControlService(
        controls=[
            KillSwitchGuard(kill_switch_registry),
            BlastRadiusGuard(
                policy=_default_blast_radius_policy(profile_policy),
                analyzer=StaticBlastRadiusAnalyzer(action_catalog),
            ),
            CircuitBreakerGuard(
                circuit_breaker_store,
                CircuitBreakerPolicy(max_consecutive_failures=profile_policy.circuit_breaker_max_consecutive_failures),
            ),
            DecisionSandboxGuard(
                PredicateSandboxExecutor((lambda ctx: _reject_negative_amount(ctx, policy=profile_policy),))
            ),
            ActionBudgetGuard(
                action_budget_ledger,
                ActionBudget(
                    max_cost=profile_policy.action_budget_max_cost,
                    max_actions=profile_policy.action_budget_max_actions,
                ),
                action_catalog,
            ),
            RiskScoreGuard(RiskScorer(policy=scorer_policy), policy=guard_policy),
            RewardGuard(
                RewardGuardPolicy(
                    min_reward=reward_defaults.min_reward,
                    min_margin=reward_defaults.min_margin,
                    zero_value=reward_defaults.zero_value,
                )
            ),
            MultiStepApprovalGuard(
                approval_repository,
                ApprovalPolicy(
                    min_approvals=profile_policy.approval_min_approvals,
                    action_prefixes=profile_policy.default_approval_prefixes,
                ),
                action_catalog,
            ),
            SimulationGate(
                SimulationGatePolicy(
                    required_for_prefixes=profile_policy.simulation_gate_prefixes,
                    min_score=profile_policy.simulation_gate_min_score,
                ),
                action_catalog,
                simulation_evidence_verifier,
            ),
            RunawayLoopGuard(
                runaway_loop_store,
                repetition_threshold=profile_policy.runaway_loop_repetition_threshold,
                catalog=action_catalog,
            ),
        ]
    )


def build_default_profile(
    policy: SafetyProfilePolicy | None = None,
    *,
    risk_scorer_policy: RiskScorerPolicy | None = None,
    risk_guard_policy: RiskScoreGuardPolicy | None = None,
    reward_guard_defaults: RewardGuardPolicyDefaults | None = None,
    persistent: bool = False,
    tenant_config_store: InMemoryTenantConfigStore | None = None,
) -> SafetyControlProfile:
    profile_policy = policy or DEFAULT_SAFETY_PROFILE_POLICY
    scorer_policy = risk_scorer_policy or DEFAULT_RISK_SCORER_POLICY
    guard_policy = risk_guard_policy or DEFAULT_RISK_SCORE_GUARD_POLICY
    reward_defaults = reward_guard_defaults or DEFAULT_REWARD_GUARD_POLICY_DEFAULTS

    if tenant_config_store is None:
        tenant_config_store = PersistentTenantConfigStore() if persistent else InMemoryTenantConfigStore()
    key_registry = SafetyKeyRegistry()
    policy_manifest_signer = PolicyManifestSigner(key_registry=key_registry)
    policy_trust_chain = PolicyTrustChain(path=safety_jsonl_path('policy_trust_chain'), snapshot_path=safety_jsonl_path('policy_trust_chain_snapshot')) if persistent else PolicyTrustChain()
    tenant_policy_resolver = TenantSafetyPolicyResolver(tenant_config_store, manifest_signer=policy_manifest_signer, trust_chain=policy_trust_chain)
    kill_switch_registry = InMemoryKillSwitchRegistry()
    circuit_breaker_store = SqliteCircuitBreakerStore(sqlite_path=safety_sqlite_path('circuit_breaker')) if persistent else InMemoryCircuitBreakerStore()
    circuit_breaker_feedback = CircuitBreakerFeedback(
        circuit_breaker_store,
        threshold=profile_policy.circuit_breaker_max_consecutive_failures,
    )
    action_budget_ledger = SqliteActionBudgetLedger(sqlite_path=safety_sqlite_path('action_budget')) if persistent else InMemoryActionBudgetLedger()
    approval_repository = SqliteApprovalRepository(sqlite_path=safety_sqlite_path('approval')) if persistent else InMemoryApprovalRepository()
    runaway_loop_store = SqliteRunawayLoopStore(
        sqlite_path=safety_sqlite_path('runaway_loop'),
        maxlen=max(profile_policy.runaway_loop_repetition_threshold + 2, 5),
    ) if persistent else InMemoryRunawayLoopStore()
    rollback_registry = InMemoryRollbackRegistry()
    rollback_plan_store = SqliteRollbackPlanStore(sqlite_path=safety_sqlite_path('rollback_plans')) if persistent else InMemoryRollbackPlanStore()
    action_catalog = build_default_action_catalog()
    tenant_metrics_registry = TenantMetricsRegistry()
    rollback_verifier = RollbackVerifier()
    safety_supervisor = SafetySupervisor(metrics_registry=tenant_metrics_registry, trust_chain=policy_trust_chain, rollback_verifier=rollback_verifier)
    event_store = JsonlSafetyEventStore(path=safety_jsonl_path('safety_events'), metrics_registry=tenant_metrics_registry, supervisor=safety_supervisor)
    simulation_evidence_verifier = SimulationEvidenceVerifier()
    import os
    strict_boot = str(os.getenv('BUSINESAIOS_SAFETY_BOOT_STRICT') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    integrity_report = SafetyBootIntegrityChecker().verify(manifest_signer=policy_manifest_signer, trust_chain=policy_trust_chain, strict=strict_boot)
    if (strict_boot or persistent) and not integrity_report.healthy:
        raise ValueError('safety boot integrity check failed: ' + ','.join(integrity_report.failures))

    return SafetyControlProfile(
        action_controls=build_action_controls(
            profile_policy=profile_policy,
            scorer_policy=scorer_policy,
            guard_policy=guard_policy,
            reward_defaults=reward_defaults,
            kill_switch_registry=kill_switch_registry,
            circuit_breaker_store=circuit_breaker_store,
            action_budget_ledger=action_budget_ledger,
            approval_repository=approval_repository,
            runaway_loop_store=runaway_loop_store,
            action_catalog=action_catalog,
            simulation_evidence_verifier=simulation_evidence_verifier,
        ),
        kill_switch_registry=kill_switch_registry,
        circuit_breaker_store=circuit_breaker_store,
        circuit_breaker_feedback=circuit_breaker_feedback,
        action_budget_ledger=action_budget_ledger,
        approval_repository=approval_repository,
        runaway_loop_store=runaway_loop_store,
        rollback_planner=RollbackPlanner(rollback_registry, rollback_plan_store, rollback_verifier),
        action_catalog=action_catalog,
        tenant_policy_resolver=tenant_policy_resolver,
        event_store=event_store,
        simulation_evidence_verifier=simulation_evidence_verifier,
        tenant_metrics_registry=tenant_metrics_registry,
        policy_manifest_signer=policy_manifest_signer,
        policy_trust_chain=policy_trust_chain,
        rollback_verifier=rollback_verifier,
        safety_supervisor=safety_supervisor,
    )


def build_tenant_profile(*, tenant_id: str, base_profile: SafetyControlProfile | None = None) -> SafetyProfilePolicy:
    profile = base_profile or build_default_profile()
    return profile.tenant_policy_resolver.resolve_profile_policy(tenant_id)
