from __future__ import annotations

from dataclasses import asdict
from typing import Any
from collections.abc import Mapping

from execution.business_memory_policy import BusinessMemoryPolicy

CANON_BUSINESS_MEMORY_PROJECTION_OWNER = True


def _memory_owner():
    from execution import business_operating_memory as owner
    return owner


def canonicalize_business_memory_payload(
    payload: Mapping[str, Any] | None,
    *,
    policy: BusinessMemoryPolicy | None = None,
):
    return _memory_owner().canonicalize_business_memory_payload(payload, policy=policy)


def project_business_memory_evidence(payload: Mapping[str, Any] | None, *, policy: BusinessMemoryPolicy | None = None) -> dict[str, Any]:
    return canonicalize_business_memory_payload(payload, policy=policy).to_evidence_payload()


def project_business_memory_summary(payload: Mapping[str, Any] | None, *, policy: BusinessMemoryPolicy | None = None) -> dict[str, Any]:
    return canonicalize_business_memory_payload(payload, policy=policy).to_summary_payload()


def project_business_memory_governance_summary(payload: Mapping[str, Any] | None, *, policy: BusinessMemoryPolicy | None = None) -> dict[str, Any]:
    canonical_policy = policy or BusinessMemoryPolicy()
    raw_payload = dict(payload or {})
    summary = canonicalize_business_memory_payload(raw_payload, policy=canonical_policy).to_summary_payload()
    active_goals = sorted(canonical_policy.sanitize_goal_list(summary.get('active_goals') or []))
    recurring_failures = sorted(canonical_policy.sanitize_scalar_sequence(summary.get('recurring_failures') or [], item_max_length=128, limit=canonical_policy.max_failures))
    recurring_wins = sorted(canonical_policy.sanitize_scalar_sequence(summary.get('recurring_wins') or [], item_max_length=128, limit=canonical_policy.max_wins))
    anti_patterns = sorted(canonical_policy.sanitize_scalar_sequence(summary.get('anti_patterns') or raw_payload.get('anti_patterns') or [], item_max_length=128, limit=canonical_policy.max_anti_patterns))
    return {
        'tenant_id': canonical_policy.sanitize_text(summary.get('tenant_id'), max_length=128),
        'business_id': canonical_policy.sanitize_text(summary.get('business_id'), max_length=128),
        'business_profile': canonical_policy.sanitize_mapping(summary.get('business_profile'), limit=canonical_policy.max_profile_fields, value_max_length=canonical_policy.max_summary_length),
        'total_runs': canonical_policy.clamp_non_negative_int(summary.get('total_runs')),
        'completed_runs': canonical_policy.clamp_non_negative_int(summary.get('completed_runs')),
        'failed_runs': canonical_policy.clamp_non_negative_int(summary.get('failed_runs')),
        'average_goal_score': canonical_policy.clamp_goal_score(summary.get('average_goal_score')),
        'active_goals': active_goals,
        'learned_preferences': canonical_policy.sanitize_mapping(summary.get('learned_preferences'), limit=canonical_policy.max_preferences, value_max_length=canonical_policy.max_summary_length),
        'operating_constraints': canonical_policy.sanitize_mapping(summary.get('operating_constraints'), limit=canonical_policy.max_constraint_fields, value_max_length=canonical_policy.max_summary_length),
        'recurring_failures': recurring_failures,
        'recurring_wins': recurring_wins,
        'anti_patterns': anti_patterns,
        'trends': canonical_policy.sanitize_feedback_payload(summary.get('trends') or {}),
        'evidence_only': True,
        'must_not_issue_decision': True,
        'must_not_unlock_effects': True,
    }


def project_business_memory_profile(payload: Mapping[str, Any] | None, *, policy: BusinessMemoryPolicy | None = None) -> dict[str, str]:
    canonical_policy = policy or BusinessMemoryPolicy()
    memory = canonicalize_business_memory_payload(payload, policy=canonical_policy)
    return canonical_policy.sanitize_mapping(memory.business_profile, limit=canonical_policy.max_profile_fields, value_max_length=canonical_policy.max_summary_length)


def project_business_memory_recent_runs(payload: Mapping[str, Any] | None, *, policy: BusinessMemoryPolicy | None = None, limit: int = 10) -> list[dict[str, Any]]:
    canonical_policy = policy or BusinessMemoryPolicy()
    memory = canonicalize_business_memory_payload(payload, policy=canonical_policy)
    bounded_limit = max(0, min(int(limit), int(canonical_policy.max_recent_runs)))
    return [asdict(item) for item in memory.recent_runs[:bounded_limit]]


def project_business_memory_patterns(payload: Mapping[str, Any] | None, *, policy: BusinessMemoryPolicy | None = None) -> dict[str, list[dict[str, Any]]]:
    canonical_policy = policy or BusinessMemoryPolicy()
    state_context = canonicalize_business_memory_payload(payload, policy=canonical_policy).to_state_context_payload(policy=canonical_policy)
    return {
        'recurring_failures': [dict(item) for item in list(state_context.get('recurring_failures') or [])],
        'recurring_wins': [dict(item) for item in list(state_context.get('recurring_wins') or [])],
        'anti_patterns': [dict(item) for item in list(state_context.get('anti_patterns') or [])],
    }


def project_business_memory_state_context(payload: Mapping[str, Any] | None, *, policy: BusinessMemoryPolicy | None = None) -> dict[str, Any]:
    canonical_policy = policy or BusinessMemoryPolicy()
    return canonicalize_business_memory_payload(payload, policy=canonical_policy).to_state_context_payload(policy=canonical_policy)


def project_business_memory_contract_bundle(payload: Mapping[str, Any] | None, *, policy: BusinessMemoryPolicy | None = None, recent_runs_limit: int = 10) -> dict[str, Any]:
    canonical_policy = policy or BusinessMemoryPolicy()
    memory = canonicalize_business_memory_payload(payload, policy=canonical_policy)
    evidence = memory.to_evidence_payload()
    state_context = memory.to_state_context_payload(policy=canonical_policy)
    bounded_limit = max(0, min(int(recent_runs_limit), int(canonical_policy.max_recent_runs)))
    recent_runs = [asdict(item) for item in memory.recent_runs[:bounded_limit]]
    patterns = {
        'recurring_failures': [dict(item) for item in state_context.get('recurring_failures') or []],
        'recurring_wins': [dict(item) for item in state_context.get('recurring_wins') or []],
        'anti_patterns': [dict(item) for item in state_context.get('anti_patterns') or []],
    }
    return {
        'evidence': evidence,
        'summary': memory.to_summary_payload(),
        'governance_summary': project_business_memory_governance_summary(evidence, policy=canonical_policy),
        'profile': canonical_policy.sanitize_mapping(
            memory.business_profile,
            limit=canonical_policy.max_profile_fields,
            value_max_length=canonical_policy.max_summary_length,
        ),
        'recent_runs': recent_runs,
        'patterns': patterns,
        'state_context': state_context,
    }


def project_business_memory_feedback_snapshot(payload: Mapping[str, Any] | None, *, policy: BusinessMemoryPolicy | None = None) -> dict[str, Any]:
    canonical_policy = policy or BusinessMemoryPolicy()
    bundle = project_business_memory_contract_bundle(payload, policy=canonical_policy, recent_runs_limit=5)
    evidence = dict(bundle.get('evidence') or {})
    governance_summary = dict(bundle.get('governance_summary') or {})
    recent_runs = list(bundle.get('recent_runs') or [])
    trends = dict(dict(bundle.get('state_context') or {}).get('trends') or {})
    recent_external_refs = canonical_policy.sanitize_scalar_sequence(evidence.get('recent_external_refs') or evidence.get('external_refs') or [], item_max_length=256, limit=8)
    verified_outcomes_count = canonical_policy.clamp_non_negative_int(evidence.get('verified_outcomes_count') or len(list(evidence.get('last_verified_outcomes') or [])))
    return {
        'business_profile': canonical_policy.sanitize_mapping(governance_summary.get('business_profile') or evidence.get('business_profile') or {}, limit=canonical_policy.max_profile_fields, value_max_length=canonical_policy.max_summary_length),
        'active_goals': list(governance_summary.get('active_goals') or []),
        'recent_external_refs': recent_external_refs,
        'verified_outcomes_count': verified_outcomes_count,
        'recent_runs': [dict(item) for item in recent_runs],
        'trends': canonical_policy.sanitize_feedback_payload(trends),
        'evidence_only': True,
        'must_not_issue_decision': True,
        'must_not_unlock_effects': True,
    }


def project_business_memory_meta_payloads(payload: Mapping[str, Any] | None, *, policy: BusinessMemoryPolicy | None = None, recent_runs_limit: int = 10) -> dict[str, dict[str, Any]]:
    bundle = project_business_memory_contract_bundle(payload, policy=policy, recent_runs_limit=recent_runs_limit)
    return {
        'business_memory': dict(bundle.get('evidence') or {}),
        'business_memory_evidence': dict(bundle.get('state_context') or {}),
        'business_memory_summary': dict(bundle.get('governance_summary') or {}),
    }
