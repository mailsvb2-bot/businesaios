from execution.economic_scope_profile import EconomicScopeProfileResolver
from execution.economic_retention_policy import EconomicRetentionPolicy


def test_scope_profile_resolver_picks_regulated_profile() -> None:
    resolver = EconomicScopeProfileResolver(base_retention_policy={'max_feedback_rows': 250, 'max_age_days': 30})
    profile = resolver.resolve(
        action={'tenant_id': 'tenant-1', 'business_id': 'biz-1', 'tenant_tier': 'enterprise', 'business_tier': 'regulated'},
        execution_receipt={},
        economic_policy={'survival_mode': 'normal'},
    )
    assert profile.profile_name == 'regulated'
    assert profile.retention_policy['max_age_days'] == 30  # base overrides profile default
    assert profile.retention_policy['max_snapshot_age_days'] == 365


def test_scope_profile_resolver_picks_guarded_profile_when_survival() -> None:
    resolver = EconomicScopeProfileResolver(base_retention_policy={'max_feedback_rows': 250})
    profile = resolver.resolve(
        action={'tenant_id': 'tenant-2', 'business_id': 'biz-2'},
        execution_receipt={},
        economic_policy={'survival_mode': 'survival', 'operator_required': True},
    )
    assert profile.profile_name == 'guarded'
    policy = EconomicRetentionPolicy.from_mapping(profile.retention_policy)
    assert policy.max_feedback_rows == 250  # base override preserved
    assert policy.max_trace_age_days == 90
